# base image
FROM node:22.22.1-alpine AS base
LABEL maintainer="takatost@gmail.com"

# if you located in China, you can use aliyun mirror to speed up
# RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# if you located in China, you can use taobao registry to speed up
# RUN npm config set registry https://registry.npmmirror.com

RUN apk add --no-cache tzdata
RUN corepack enable
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ARG NEXT_PUBLIC_BASE_PATH=""
ENV NEXT_PUBLIC_BASE_PATH="$NEXT_PUBLIC_BASE_PATH"


# install packages
FROM base AS packages

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /app/
COPY web/package.json /app/web/
COPY e2e/package.json /app/e2e/
COPY sdks/nodejs-client/package.json /app/sdks/nodejs-client/
COPY packages /app/packages

# Use packageManager from package.json
RUN corepack install

# Install workspace dependencies for the Docker build environment.
RUN VITE_GIT_HOOKS=0 pnpm install --frozen-lockfile

# build resources
FROM base AS builder
WORKDIR /app
COPY --from=packages /app/ .
COPY . .

WORKDIR /app/web
ENV NODE_OPTIONS="--max-old-space-size=4096"
ENV pnpm_config_verify_deps_before_run=false
RUN pnpm build && pnpm build:vinext


# production stage
FROM base AS production

ENV NODE_ENV=production
ENV EDITION=SELF_HOSTED
ENV DEPLOY_ENV=PRODUCTION
ENV CONSOLE_API_URL=http://127.0.0.1:5001
ENV APP_API_URL=http://127.0.0.1:5001
ENV MARKETPLACE_API_URL=https://marketplace.data.ai
ENV MARKETPLACE_URL=https://marketplace.data.ai
ENV PORT=3000
ENV EXPERIMENTAL_ENABLE_VINEXT=false
ENV NEXT_TELEMETRY_DISABLED=1

# set timezone
ENV TZ=UTC
RUN ln -s /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone

# Create non-root user
ARG data_uid=1001
RUN addgroup -S -g ${data_uid} data && \
    adduser -S -u ${data_uid} -G data -s /bin/ash -h /home/data data && \
    mkdir /app && \
    chown -R data:data /app


WORKDIR /app

COPY --from=builder --chown=data:data /app/web/public ./targets/next/web/public
COPY --from=builder --chown=data:data /app/web/.next/standalone ./targets/next/
COPY --from=builder --chown=data:data /app/web/.next/static ./targets/next/web/.next/static
COPY --from=builder --chown=data:data /app/web/dist/standalone ./targets/vinext

COPY --chown=data:data --chmod=755 web/docker/entrypoint.sh ./entrypoint.sh

ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

USER data
EXPOSE 3000
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
