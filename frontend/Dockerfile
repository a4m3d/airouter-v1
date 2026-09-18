# Frontend build for portable deployment (served with `serve`).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install
COPY . .
RUN yarn build

FROM node:20-alpine
WORKDIR /app
RUN yarn global add serve
COPY --from=build /app/build /app/build
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
