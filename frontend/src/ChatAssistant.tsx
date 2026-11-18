
import { useEffect, useRef, useState } from "react";
import { sendAIMessage } from "./api";

const MAX_MESSAGE_LENGTH = 2000;

const SUGGESTED_QUESTIONS = [
  "How many PTO hours do I get each year?",
  "Is the day after Thanksgiving a holiday?",
  "How far in advance do I need to request time off?",
];

const HUMAN_REVIEW_NOTICE =
  "⚠ Please confirm this with your manager or Human Resources.";

type ChatMessage = {
  id: number;
  role: "user" | "assistant" | "error";
  text: string;
  requiresHumanReview?: boolean;
};

const bubbleBase: React.CSSProperties = {
  maxWidth: "85%",
  padding: "10px 14px",
  borderRadius: "12px",
  marginBottom: "10px",
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
};

const bubbleStyles: Record<ChatMessage["role"], React.CSSProperties> = {
  user: {
    ...bubbleBase,
    marginLeft: "auto",
    background: "var(--accent-bg)",
    border: "1px solid var(--accent-border)",
    color: "var(--text-h)",
  },
  assistant: {
    ...bubbleBase,
    marginRight: "auto",
    background: "var(--code-bg)",
    border: "1px solid var(--border)",
    color: "var(--text-h)",
  },
  error: {
    ...bubbleBase,
    marginRight: "auto",
    background: "rgba(220, 38, 38, 0.08)",
    border: "1px solid rgba(220, 38, 38, 0.5)",
    color: "#dc2626",
  },
};

const ROLE_LABELS: Record<ChatMessage["role"], string> = {
  user: "You",
  assistant: "Assistant",
  error: "Error",
};

function ChatAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const nextId = useRef(1);
  const listEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages, loading]);

  function addMessage(message: Omit<ChatMessage, "id">) {
    const id = nextId.current++;
    setMessages((previous) => [...previous, { ...message, id }]);
  }

  async function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading || trimmed.length > MAX_MESSAGE_LENGTH) {
      return;
    }

    addMessage({ role: "user", text: trimmed });
    setInput("");
    setLoading(true);

    try {
      const reply = await sendAIMessage(trimmed);
      addMessage({
        role: "assistant",
        text: reply.response,
        requiresHumanReview: reply.requires_human_review,
      });
    } catch (err) {
      addMessage({
        role: "error",
        text:
          err instanceof Error && err.message
            ? err.message
            : "The AI assistant is unavailable right now. Please try again later.",
      });
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(input);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter (or Enter while composing text in an IME) adds a new line.
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void ask(input);
    }
  }

  const canAsk = input.trim().length > 0 && !loading;

  return (
    <section
      aria-labelledby="chat-assistant-heading"
      style={{
        width: "100%",
        maxWidth: "720px",
        margin: "0 auto 32px",
        padding: "0 16px",
        boxSizing: "border-box",
        textAlign: "left",
      }}
    >
      <h2 id="chat-assistant-heading">PTO Policy Assistant</h2>
      <p>
        Ask a question about the company PTO policy. The assistant cannot see
        your balance or requests and cannot approve time off.
      </p>

      <div
        role="log"
        aria-live="polite"
        aria-label="Conversation with the PTO policy assistant"
        style={{
          border: "1px solid var(--border)",
          borderRadius: "8px",
          padding: "16px",
          minHeight: "120px",
          maxHeight: "400px",
          overflowY: "auto",
          marginBottom: "12px",
        }}
      >
        {messages.length === 0 && (
          <div>
            <p style={{ marginTop: 0 }}>Try one of these questions:</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {SUGGESTED_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => void ask(question)}
                  disabled={loading}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} style={bubbleStyles[message.role]}>
            <span
              style={{
                display: "block",
                fontSize: "0.8em",
                fontWeight: 600,
                marginBottom: "4px",
              }}
            >
              {ROLE_LABELS[message.role]}
            </span>
            {message.text}
            {message.requiresHumanReview && (
              <p style={{ margin: "8px 0 0", fontWeight: 600 }}>
                {HUMAN_REVIEW_NOTICE}
              </p>
            )}
          </div>
        ))}

        {loading && <p style={{ margin: 0 }}>Assistant is thinking...</p>}

        <div ref={listEndRef} />
      </div>

      <form onSubmit={handleSubmit}>
        <label htmlFor="chat-question" style={{ display: "block", marginBottom: "4px" }}>
          Your question
        </label>
        <textarea
          id="chat-question"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_MESSAGE_LENGTH}
          rows={3}
          placeholder="e.g. How many PTO hours carry over into next year?"
          aria-describedby="chat-question-hint chat-question-count"
          style={{
            width: "100%",
            boxSizing: "border-box",
            font: "inherit",
            padding: "8px",
            resize: "vertical",
          }}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "12px",
            flexWrap: "wrap",
            marginTop: "4px",
          }}
        >
          <small id="chat-question-hint">
            Press Enter to send, Shift+Enter for a new line.
          </small>
          <small id="chat-question-count">
            {input.length.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()} characters
          </small>
        </div>
        <button type="submit" disabled={!canAsk} style={{ marginTop: "8px" }}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </form>
    </section>
  );
}

export default ChatAssistant;
