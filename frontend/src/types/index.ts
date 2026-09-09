/**
 * SocialOS Core TypeScript Type Exports.
 */

export * from "./company";
export * from "./social";

export interface HealthStatus {
  status: string;
  app: string;
  version: string;
  environment: string;
}
