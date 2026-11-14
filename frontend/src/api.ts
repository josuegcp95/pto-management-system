import { apiRequest } from "./apiClient";
import {
  mockGetCurrentUser,
  mockGetPTOBalance,
  mockCreatePTORequest,
  mockGetPTORequests,
  mockGetPTORequest,
  mockReviewPTORequest,
  mockSendAIMessage,
} from "./mockApi";

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
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API === "true";

export function getCurrentUser(): Promise<User> {
  if (USE_MOCK_API) return mockGetCurrentUser();

  return apiRequest<User>(`${BASE_PATH}/users/me`);
}

export function getPTOBalance(): Promise<PTOBalance> {
  if (USE_MOCK_API) return mockGetPTOBalance();

  return apiRequest<PTOBalance>(`${BASE_PATH}/pto/balance`);
}

export function createPTORequest(
  request: CreatePTORequest
): Promise<PTORequest> {
  if (USE_MOCK_API) return mockCreatePTORequest(request);

  return apiRequest<PTORequest>(`${BASE_PATH}/pto/requests`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getPTORequests(
  status?: PTOStatus,
  limit = 20,
  offset = 0
): Promise<PTORequestList> {
  if (USE_MOCK_API) {
    return mockGetPTORequests(status, limit, offset);
  }

  const params = new URLSearchParams();

  if (status) params.set("status", status);

  params.set("limit", String(limit));
  params.set("offset", String(offset));

  return apiRequest<PTORequestList>(
    `${BASE_PATH}/pto/requests?${params.toString()}`
  );
}

export function getPTORequest(
  requestId: number
): Promise<PTORequest> {
  if (USE_MOCK_API) return mockGetPTORequest(requestId);

  return apiRequest<PTORequest>(
    `${BASE_PATH}/pto/requests/${requestId}`
  );
}

export function reviewPTORequest(
  requestId: number,
  decision: PTOReview
): Promise<PTOReviewResult> {
  if (USE_MOCK_API) {
    return mockReviewPTORequest(requestId, decision);
  }

  return apiRequest<PTOReviewResult>(
    `${BASE_PATH}/pto/requests/${requestId}/decision`,
    {
      method: "PATCH",
      body: JSON.stringify(decision),
    }
  );
}

export function sendAIMessage(
  message: string
): Promise<AIChatResponse> {
  if (USE_MOCK_API) return mockSendAIMessage(message);

  return apiRequest<AIChatResponse>(
    `${BASE_PATH}/ai/chat`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    }
  );
}

