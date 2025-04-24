# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# https://mcr.microsoft.com/product/dotnet/sdk
FROM --platform=$BUILDPLATFORM registry.redhat.io/rhel8/dotnet-90:9.0-7 AS builder
USER root

WORKDIR /app
RUN chown -R default /app

RUN chown -R default /app \
 && mkdir -p /cartservice \
 && chown -R default /cartservice

USER default
COPY cartservice.csproj .
RUN dotnet restore cartservice.csproj

COPY . .
RUN dotnet publish cartservice.csproj \
    --no-self-contained \
    -c release \
    -o /cartservice

# https://mcr.microsoft.com/product/dotnet/runtime-deps
FROM registry.redhat.io/rhel8/dotnet-90:9.0-7

WORKDIR /app
COPY --from=builder /cartservice .
EXPOSE 7070
ENV DOTNET_EnableDiagnostics=0 \
    ASPNETCORE_HTTP_PORTS=7070
USER 1000
ENTRYPOINT ["/app/cartservice"]
