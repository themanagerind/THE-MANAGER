# Production image — builds the Vite PWA bundle, then serves it with
# nginx (see nginx.conf for the reverse-proxy wiring this app's own
# relative API baseURL depends on — src/api/client.ts, vite.config.ts).
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Opts into the official image's own /docker-entrypoint.d/
# 15-local-resolvers.envsh — that script is a no-op unless this exact
# var is set to something non-empty (see its source: `[ "${NGINX_
# ENTRYPOINT_LOCAL_RESOLVERS:-}" ] || return 0`). Once it runs, it
# exports a DIFFERENT var, NGINX_LOCAL_RESOLVERS, which is what
# nginx.conf actually references.
ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
ENV BACKEND_UPSTREAM_URL=http://backend.railway.internal:8000
# Deployed as a *.template* (not straight to conf.d/) so the official
# image's own entrypoint runs envsubst on it — nginx.conf references
# ${NGINX_LOCAL_RESOLVERS}, which only that step fills in. envsubst
# here only ever touches names that are actual env vars, so nginx's own
# $variables ($host, $uri, etc.) in the file are untouched.
COPY nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
