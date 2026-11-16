
import { useEffect, useState } from "react";
import { getPTORequests, reviewPTORequest } from "./api";
import type { PTORequest, PTOReview } from "./types";

function ManagerDashboard() {
  const [requests, setRequests] = useState<PTORequest[]>([]);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    async function loadRequests() {
      try {
        const result = await getPTORequests("pending");
        setRequests(result.requests.filter(
          (request) => request.status === "pending"
        ));
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load pending requests."
        );
      } finally {
        setLoading(false);
      }
    }

    void loadRequests();
  }, []);

  async function handleDecision(
    requestId: number,
    decision: PTOReview["decision"]
  ) {
    setError("");
    setSuccess("");
    setReviewingId(requestId);

    try {
      const managerComment = comments[requestId]?.trim();

      await reviewPTORequest(requestId, {
        decision,
        ...(managerComment
          ? { manager_comment: managerComment }
          : {}),
      });

      setRequests((previous) =>
        previous.filter(
          (request) => request.request_id !== requestId
        )
      );

      setSuccess(
        `PTO request #${requestId} ${decision} successfully.`
      );

      setComments((previous) => {
        const updated = { ...previous };
        delete updated[requestId];
        return updated;
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to review PTO request."
      );
    } finally {
      setReviewingId(null);
    }
  }

  return (
    <section>
      <h2>Manager Dashboard</h2>
      <p>Review and manage employee PTO requests.</p>

      {error && (
        <p role="alert" style={{ color: "red" }}>
          {error}
        </p>
      )}

      {success && (
        <p role="status" style={{ color: "green" }}>
          {success}
        </p>
      )}

      <h3>Pending Requests</h3>

      {loading ? (
        <p>Loading pending requests...</p>
      ) : requests.length === 0 ? (
        <p>No pending requests.</p>
      ) : (
        requests.map((request) => (
          <article
            key={request.request_id}
            style={{
              border: "1px solid #ccc",
              borderRadius: "8px",
              padding: "16px",
              marginBottom: "16px",
            }}
          >
            <h4>{request.employee_name}</h4>

            <p>
              Requested dates: {request.start_date} to{" "}
              {request.end_date}
            </p>

            <p>Requested hours: {request.hours}</p>
            <p>Status: {request.status}</p>

            {request.reason && (
              <p>Reason: {request.reason}</p>
            )}

            {request.flags.map((flag) => (
              <p
                key={flag.code}
                style={{ color: "#d97706" }}
              >
                ⚠️ {flag.code}: {flag.message}
              </p>
            ))}

            <textarea
              aria-label="Manager comment"
              placeholder="Optional manager comment"
              value={comments[request.request_id] ?? ""}
              disabled={reviewingId !== null}
              onChange={(event) =>
                setComments((previous) => ({
                  ...previous,
                  [request.request_id]: event.target.value,
                }))
              }
            />

            <div style={{ marginTop: "10px" }}>
              <button
                disabled={reviewingId !== null}
                onClick={() =>
                  void handleDecision(
                    request.request_id,
                    "approved"
                  )
                }
              >
                {reviewingId === request.request_id
                  ? "Processing..."
                  : "Approve"}
              </button>

              <button
                disabled={reviewingId !== null}
                onClick={() =>
                  void handleDecision(
                    request.request_id,
                    "denied"
                  )
                }
                style={{ marginLeft: "10px" }}
              >
                {reviewingId === request.request_id
                  ? "Processing..."
                  : "Deny"}
              </button>
            </div>
          </article>
        ))
      )}
    </section>
  );
}

export default ManagerDashboard;
