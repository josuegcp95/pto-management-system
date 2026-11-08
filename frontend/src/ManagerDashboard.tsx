
import { useState } from "react";

type PTORequest = {
  id: number;
  employee: string;
  startDate: string;
  endDate: string;
  status: "Pending" | "Approved" | "Denied";
  flag: string | null;
  comment?: string;
};

const sampleRequests: PTORequest[] = [
  {
    id: 1,
    employee: "Alex Morgan",
    startDate: "2026-11-18",
    endDate: "2026-11-20",
    status: "Pending",
    flag: null,
  },
  {
    id: 2,
    employee: "Jordan Lee",
    startDate: "2026-11-23",
    endDate: "2026-11-27",
    status: "Pending",
    flag: "Potential staffing conflict during holiday week",
  },
  {
    id: 3,
    employee: "Taylor Smith",
    startDate: "2026-12-03",
    endDate: "2026-12-04",
    status: "Pending",
    flag: null,
  },
];

function ManagerDashboard() {
  const [requests, setRequests] = useState(sampleRequests);
  const [comments, setComments] = useState<Record<number, string>>({});

  function handleDecision(id: number, status: "Approved" | "Denied") {
    setRequests((previous) =>
      previous.map((request) =>
        request.id === id
          ? { ...request, status, comment: comments[id] ?? "" }
          : request
      )
    );
  }

  return (
    <section>
      <h2>Manager Dashboard</h2>
      <p>Review and manage employee PTO requests.</p>

      <h3>Pending Requests</h3>

      {requests.filter((request) => request.status === "Pending").length === 0 && (
        <p>No pending requests.</p>
      )}

      {requests.map((request) => (
        <article
          key={request.id}
          style={{
            border: "1px solid #ccc",
            borderRadius: "8px",
            padding: "16px",
            marginBottom: "16px",
          }}
        >
          <h4>{request.employee}</h4>
          <p>
            Requested dates: {request.startDate} to {request.endDate}
          </p>
          <p>Status: {request.status}</p>

          {request.flag && (
            <p style={{ color: "#d97706" }}>
              ⚠️ {request.flag}
            </p>
          )}

          {request.status === "Pending" && (
            <>
              <textarea
                placeholder="Optional manager comment"
                value={comments[request.id] ?? ""}
                onChange={(event) =>
                  setComments((previous) => ({
                    ...previous,
                    [request.id]: event.target.value,
                  }))
                }
              />

              <div style={{ marginTop: "10px" }}>
                <button
                  onClick={() => handleDecision(request.id, "Approved")}
                >
                  Approve
                </button>

                <button
                  onClick={() => handleDecision(request.id, "Denied")}
                  style={{ marginLeft: "10px" }}
                >
                  Deny
                </button>
              </div>
            </>
          )}
        </article>
      ))}
    </section>
  );
}

export default ManagerDashboard;
