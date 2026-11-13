export type UserRole = "employee" | "manager";

export type PTOStatus = "pending" | "approved" | "denied";


export interface User {
  employee_id: number;
  name: string;
  email: string;
  role: UserRole;
  manager_id: number | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}


export interface PTOBalance {
  employee_id: number;
  total_hours: number;
  used_hours: number;
  pending_hours: number;
  available_hours: number;
}

export interface CreatePTORequest {
  start_date: string;
  end_date: string;
  reason?: string;
}

export interface PTORequest {
  request_id: number;
  employee_id: number;
  start_date: string;
  end_date: string;
  reason?: string | null;
  status: PTOStatus;
  created_at?: string;
  rule_flags?: string[];
  rule_explanations?: string[];
}

export interface PTORequestList {
  requests: PTORequest[];
  total: number;
  limit: number;
  offset: number;
}

export interface PTOReview {
  decision: "approved" | "denied";
  manager_comment?: string;
}

export interface PTOReviewResult {
  request_id: number;
  status: "approved" | "denied";
  reviewed_by: number;
  reviewed_at: string;
}

export interface AIChatRequest {
  message: string;
}

export interface AIChatResponse {
  response: string;
  source: string;
  requires_human_review: boolean;
}
