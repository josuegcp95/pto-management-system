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

// Demonstration data only. Nothing is saved to the backend.
const mockUser: User = {
  employee_id: 215,
  name: "Alex Morgan",
  role: "employee",
};

let requests: PTORequest[] = [
  {
    request_id: 1042,
    employee_id: 215,
    start_date: "2026-11-18",
    end_date: "2026-11-20",
    reason: "Vacation",
    status: "pending",
    created_at: "2026-11-10T14:00:00Z",
  },
  {
    request_id: 1043,
    employee_id: 215,
    start_date: "2026-11-25",
    end_date: "2026-11-27",
    reason: "Family event",
    status: "approved",
    created_at: "2026-11-09T10:00:00Z",
  },
];

export async function mockGetCurrentUser(): Promise<User> {
  return mockUser;
}

export async function mockLogin(
  email: string,
  password: string
): Promise<{
  access_token: string;
  token_type: string;
  user: User;
}> {
  if (!email.trim() || !password.trim()) {
    throw new Error("Email and password are required.");
  }

  const role = email.toLowerCase().startsWith("manager@")
    ? "manager"
    : "employee";

  const user: User = {
    employee_id: role === "manager" ? 310 : 215,
    name: role === "manager" ? "Demo Manager" : "Alex Morgan",
    email,
    role,
    manager_id: role === "manager" ? null : 310,
  };

  return {
    access_token: "mock-demo-token",
    token_type: "bearer",
    user,
  };
}

export async function mockGetPTOBalance(): Promise<PTOBalance> {
  return {
    employee_id: 215,
    total_hours: 120,
    used_hours: 40,
    pending_hours: 16,
    available_hours: 64,
  };
}

export async function mockCreatePTORequest(
  request: CreatePTORequest
): Promise<PTORequest> {
  if (request.start_date > request.end_date) {
    throw new Error("Start date must be before end date.");
  }

  if ((request.reason?.length ?? 0) > 500) {
    throw new Error("Reason cannot exceed 500 characters.");
  }

  const newRequest: PTORequest = {
    request_id: Math.max(0, ...requests.map(r => r.request_id)) + 1,
    employee_id: mockUser.employee_id,
    ...request,
    status: "pending",
    created_at: new Date().toISOString(),
  };

  requests = [...requests, newRequest];
  return newRequest;
}

export async function mockGetPTORequests(
  status?: PTOStatus,
  limit = 20,
  offset = 0
): Promise<PTORequestList> {
  const filtered = status
    ? requests.filter(r => r.status === status)
    : requests;

  return {
    requests: filtered.slice(offset, offset + limit),
    total: filtered.length,
    limit,
    offset,
  };
}

export async function mockGetPTORequest(
  requestId: number
): Promise<PTORequest> {
  const request = requests.find(r => r.request_id === requestId);

  if (!request) {
    throw new Error("PTO request not found.");
  }

  return request;
}

export async function mockReviewPTORequest(
  requestId: number,
  decision: PTOReview
): Promise<PTOReviewResult> {
  const request = requests.find(r => r.request_id === requestId);

  if (!request) {
    throw new Error("PTO request not found.");
  }

  if (request.status !== "pending") {
    throw new Error("This request has already been reviewed.");
  }

  request.status = decision.decision;

  return {
    request_id: requestId,
    status: decision.decision,
    reviewed_by: 310,
    reviewed_at: new Date().toISOString(),
  };
}

export async function mockSendAIMessage(
  message: string
): Promise<AIChatResponse> {
  if (!message.trim() || message.length > 2000) {
    throw new Error("Message must contain 1 to 2000 characters.");
  }

  return {
    response:
      "This is a demonstration response. The AI assistant is not connected.",
    source: "mock",
    requires_human_review: true,
  };
}
