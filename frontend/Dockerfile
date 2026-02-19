# Frontend Dockerfile for React Application
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Set environment variables
ENV NODE_ENV=development

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port for development server
EXPOSE 3000

# Command to run the development server with hot-reload
CMD ["npm", "start"]
