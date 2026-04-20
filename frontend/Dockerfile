# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Build-time API URL (can be overridden in Railway)
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


# Serve stage
FROM nginx:alpine

# Copy build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config template
COPY ./nginx.conf /etc/nginx/templates/default.conf.template

# Expose (not mandatory but fine)
EXPOSE 80

# Replace PORT dynamically and start nginx
CMD ["sh", "-c", "envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]