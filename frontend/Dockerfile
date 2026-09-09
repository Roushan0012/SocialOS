FROM node:22-alpine

WORKDIR /app

# Install dependencies first for caching
COPY package.json ./
RUN npm install

# Copy application source code
COPY . .

# Expose Next.js port
EXPOSE 3000

# Default development command
CMD ["npm", "run", "dev"]
