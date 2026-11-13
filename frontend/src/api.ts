import { apiRequest } from "./apiClient";

import type {
  User,
  PTOBalance,
  PTOStatus,
  PTORequest,
  PTORequestList,
  CreatePTORequest,
  PTOReview,
  PTOReviewResult,
  AIChatResponse,
} from "./types";

const BASE_PATH = "/api/v1";

// Get the currently logged-in employee or manager.
export function getCurrentUser(): Promise<User> {
  return apiRequest<User>(`${BASE_PATH}/users/me`);
}

// Get an employee's PTO balance.
export function getPTOBalance(): Promise<PTOBalance> {
  return apiRequest<PTOBalance>(`${BASE_PATH}/pto/balance`);
}

// Submit a new PTO request.
export function createPTORequest(
  request: CreatePTORequest
): Promise<PTORequest> {
  return apiRequest<PTORequest>(`${BASE_PATH}/pto/requests`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// Retrieve PTO requests with optional filters.
export function getPTORequests(
  status?: PTOStatus,
  limit = 20,
  offset = 0
): Promise<PTORequestList> {
  const params = new URLSearchParams();

  if (status) {
    params.set("status", status);
  }

  params.set("limit", String(limit));
  params.set("offset", String(offset));

  return apiRequest<PTORequestList>(
    `${BASE_PATH}/pto/requests?${params.toString()}`
  );
}

// Retrieve a specific PTO request.
export function getPTORequest(
  requestId: number
): Promise<PTORequest> {
  return apiRequest<PTORequest>(
    `${BASE_PATH}/pto/requests/${requestId}`
  );
}

// Approve or deny a PTO request.
export function reviewPTORequest(
  requestId: number,
  decision: PTOReview
): Promise<PTOReviewResult> {
  return apiRequest<PTOReviewResult>(
    `${BASE_PATH}/pto/requests/${requestId}/decision`,
    {
      method: "PATCH",
      body: JSON.stringify(decision),
    }
  );
}

// Send a question to the AI policy assistant.
export function sendAIMessage(
  message: string
): Promise<AIChatResponse> {
  return apiRequest<AIChatResponse>(
    `${BASE_PATH}/ai/chat`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    }
  );
}
