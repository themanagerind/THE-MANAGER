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
# Deployed as a *.template* (not straight to conf.d/) so the official
# image's own entrypoint runs envsubst on it — nginx.conf references
# ${NGINX_ENTRYPOINT_LOCAL_RESOLVERS}, which only that step fills in.
# envsubst here only ever touches names that are actual env vars, so
# nginx's own $variables ($host, $uri, etc.) in the file are untouched.
COPY nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
