// Copyright 2018 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

const axios = require('axios');
const grpc = require('@grpc/grpc-js');
const cardValidator = require('simple-card-validator');
const { v4: uuidv4 } = require('uuid');
const pino = require('pino');

// Configure Triton server URL and model details via environment variables
const TRITON_URL = process.env.TRITON_URL;
if (!TRITON_URL) {
  throw new Error('Environment variable TRITON_URL is required');
}
const MODEL_NAME = process.env.FRAUD_MODEL_NAME || 'fraud_model';
const MODEL_VERSION = process.env.FRAUD_MODEL_VERSION || '1';

// Enable or disable fraud detection
const ENABLE_FRAUD_DETECTION = process.env.ENABLE_FRAUD_DETECTION === 'true';

const logger = pino({
  name: 'paymentservice-charge',
  messageKey: 'message',
  formatters: { level (lvl) { return { severity: lvl }; } },
  base: null
});

// Map shipping country to integer index as used in model training
const countryToIdx = {
  'United States': 0,
  'Canada': 1,
  'United Kingdom': 2,
  'Australia': 3,
  'Germany': 4,
  'France': 5,
  'Japan': 6,
  'South Korea': 7,
  'China': 8,
  'Russia': 9,
  'Nigeria': 10
};

class CreditCardError extends Error {
  constructor (message) {
    super(message);
    this.code = grpc.status.INVALID_ARGUMENT;
  }
}

class InvalidCreditCard extends CreditCardError {
  constructor (cardType) {
    super(`Credit card info is invalid`);
  }
}

class UnacceptedCreditCard extends CreditCardError {
  constructor (cardType) {
    super(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`);
  }
}

class ExpiredCreditCard extends CreditCardError {
  constructor (number, month, year) {
    super(`Your credit card (ending ${number.substr(-4)}) expired on ${month}/${year}`);
  }
}

/**
 * Verifies the credit card and performs an external fraud check via Triton.
 * @param {*} request  The ChargeRequest gRPC object
 * @returns transaction_id - uuid if approved
 * @throws CreditCardError on validation or fraud detection
 */
module.exports = async function charge (request) {
  const { amount, credit_card: creditCard, shipping_country } = request;
  // Build numeric amount
  const totalAmount = Number(amount.units) + amount.nanos / 1e9;

  // Optional fraud detection
  if (ENABLE_FRAUD_DETECTION) {
    try {
      const countryIdx = countryToIdx[shipping_country] ?? 0;
      const inferReq = {
        inputs: [
          { name: 'country', datatype: 'INT64', shape: [1], data: [countryIdx] },
          { name: 'amount',  datatype: 'FP32', shape: [1], data: [totalAmount] }
        ]
      };
      const resp = await axios.post(
        `${TRITON_URL}/v2/models/${MODEL_NAME}/versions/${MODEL_VERSION}/infer`,
        inferReq
      );
      const score = resp.data.outputs[0].data[0];
      logger.info(`🧠 Fraud score: ${score} for total amount: ${amount.currency_code}${totalAmount} and shipping country: ${shipping_country}`);
    } catch (err) {
      if (err.isAxiosError) {
        logger.error(`Fraud model call failed: ${err.message}`);
        // Block all if service unavailable.
        throw new CreditCardError('Fraud check service unavailable');
      }
      throw err;
    }
  } else {
    logger.info('Fraud detection disabled');
  }

  // Card validation
  const cardNumber = creditCard.credit_card_number;
  const { card_type: cardType, valid } = cardValidator(cardNumber).getCardDetails();
  if (!valid) {
    throw new InvalidCreditCard();
  }
  if (!(cardType === 'visa' || cardType === 'mastercard')) {
    throw new UnacceptedCreditCard(cardType);
  }
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();
  const { credit_card_expiration_year: year, credit_card_expiration_month: month } = creditCard;
  if ((currentYear * 12 + currentMonth) > (year * 12 + month)) { throw new ExpiredCreditCard(cardNumber.substr(-4), month, year); }

  logger.info(`Transaction processed: ${cardType} ending ${cardNumber.substr(-4)} ` +`Amount: ${amount.currency_code}${amount.units}.${amount.nanos}`);

  return { transaction_id: uuidv4() };
};
