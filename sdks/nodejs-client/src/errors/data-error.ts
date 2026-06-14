export type DATAErrorOptions = {
  statusCode?: number;
  responseBody?: unknown;
  requestId?: string;
  retryAfter?: number;
  cause?: unknown;
};

export class DATAError extends Error {
  statusCode?: number;
  responseBody?: unknown;
  requestId?: string;
  retryAfter?: number;

  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message);
    this.name = "DATAError";
    this.statusCode = options.statusCode;
    this.responseBody = options.responseBody;
    this.requestId = options.requestId;
    this.retryAfter = options.retryAfter;
    if (options.cause) {
      (this as { cause?: unknown }).cause = options.cause;
    }
  }
}

export class APIError extends DATAError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "APIError";
  }
}

export class AuthenticationError extends APIError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "AuthenticationError";
  }
}

export class RateLimitError extends APIError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "RateLimitError";
  }
}

export class ValidationError extends APIError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "ValidationError";
  }
}

export class NetworkError extends DATAError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "NetworkError";
  }
}

export class TimeoutError extends DATAError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "TimeoutError";
  }
}

export class FileUploadError extends DATAError {
  constructor(message: string, options: DATAErrorOptions = {}) {
    super(message, options);
    this.name = "FileUploadError";
  }
}
