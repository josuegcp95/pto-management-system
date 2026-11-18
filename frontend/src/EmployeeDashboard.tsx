
import { useEffect, useState } from "react";
import {
  getPTOBalance,
  createPTORequest,
  getPTORequests,
} from "./api";
import type {
  PTOBalance,
  PTORequest,
} from "./types";

function EmployeeDashboard() {
  const [balance, setBalance] = useState<PTOBalance | null>(null);
  const [requests, setRequests] = useState<PTORequest[]>([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadData() {
    try {
      setError("");

      const [balanceData, requestData] = await Promise.all([
        getPTOBalance(),
        getPTORequests(),
      ]);

      setBalance(balanceData);
      setRequests(requestData.requests);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load PTO information."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!startDate || !endDate) {
      setError("Please select both dates.");
      return;
    }

    if (startDate > endDate) {
      setError("Start date cannot be after end date.");
      return;
    }

    if (reason.length > 500) {
      setError("Reason cannot exceed 500 characters.");
      return;
    }

    setSubmitting(true);

    try {
      const newRequest = await createPTORequest({
        start_date: startDate,
        end_date: endDate,
        ...(reason.trim() ? { reason: reason.trim() } : {}),
      });

      setRequests((previous) => [newRequest, ...previous]);
      setSuccess("Your PTO request was submitted successfully.");

      setStartDate("");
      setEndDate("");
      setReason("");

      await loadData();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to submit PTO request."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p>Loading employee dashboard...</p>;
  }

  return (
    <section>
      <h2>Employee Dashboard</h2>
      <p>View your PTO balance and manage your requests.</p>

      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      {success && <p role="status" style={{ color: "green" }}>{success}</p>}

      <h3>PTO Balance</h3>

      {balance ? (
        <div>
          <p>Available Hours: {balance.available_hours}</p>
          <p>Used Hours: {balance.used_hours}</p>
          <p>Pending Hours: {balance.pending_hours}</p>
        </div>
      ) : (
        <p>Balance information unavailable.</p>
      )}

      <hr />

      <h3>Request Time Off</h3>

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="startDate">Start Date</label>
          <input
            id="startDate"
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="endDate">End Date</label>
          <input
            id="endDate"
            type="date"
            min={startDate || undefined}
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="reason">Reason (Optional)</label>
          <textarea
            id="reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            placeholder="Enter a reason for your request"
          />
        </div>

        <button type="submit" disabled={submitting}>
          {submitting ? "Submitting..." : "Submit PTO Request"}
        </button>
      </form>

      <hr />

      <h3>My Requests</h3>

      {requests.length === 0 ? (
        <p>You have no PTO requests.</p>
      ) : (
        requests.map((request) => (
          <article
            key={request.request_id}
            style={{
              border: "1px solid #ccc",
              borderRadius: "8px",
              padding: "16px",
              marginBottom: "12px",
            }}
          >
            <p>
              <strong>Dates:</strong> {request.start_date} to {request.end_date}
            </p>

            <p>
              <strong>Hours:</strong> {request.hours}
            </p>

            <p>
              <strong>Status:</strong> {request.status}
            </p>

            {request.reason && (
              <p><strong>Reason:</strong> {request.reason}</p>
            )}

            {request.manager_comment && (
              <p>
                <strong>Manager comment:</strong> {request.manager_comment}
              </p>
            )}

            {request.flags?.map((flag, index) => (
              <p key={index}>
                <strong>Policy notice:</strong> {flag.message}
              </p>
            ))}
          </article>
        ))
      )}
    </section>
  );
}

export default EmployeeDashboard;
