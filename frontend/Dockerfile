# Web image (docs/02 section 7, docs/09 section 9): static files on unprivileged nginx.
# Types, lint and tests run in CI; this only bundles.

FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a AS build
RUN npm install --global --no-audit --no-fund pnpm@12.16.1
WORKDIR /web
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm exec vite build

FROM nginxinc/nginx-unprivileged:alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e
# Security fixes published since the pinned base was built.
USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /web/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
