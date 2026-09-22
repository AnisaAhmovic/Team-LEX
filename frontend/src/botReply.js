// botReply.js
// Turns what the Django /api/answer/ endpoint sent back into a message for the
// chat window. It is in its own file so it can be tested without a browser
// (see verify_messages.mjs).
//
// There are three kinds of bot reply:
//   "answer"   - there was enough policy evidence, so we show the cited answer
//   "fallback" - there wasn't enough evidence, so we show the safe message and
//                a link to the official Policy Library instead of guessing
//   "error"    - something went wrong. This is NOT a policy answer and must
//                not look like one

export function makeBotReply(ok, httpStatus, data) {
  // Enough evidence was found and Qwen3 gave a cited answer.
  if (ok && data.status === "supported") {
    return {
      type: "answer",
      message: data.answer,
      claims: data.claims,
      sources: data.sources,
    };
  }

  // The request worked but there wasn't enough policy evidence to answer.
  // This is the normal safe fallback, so keep the escalation link.
  if (ok) {
    return {
      type: "fallback",
      message: data.message,
      escalation: data.escalation,
    };
  }

  // 400 means the question itself was the problem (for example it was too
  // short). The backend tells us what was wrong, so show that instead of
  // "try again", which wouldn't help.
  if (httpStatus === 400) {
    let message = "Please check your question and try again.";
    if (data && data.validation_error) {
      message = data.validation_error;
    }
    return {
      type: "error",
      message: message,
    };
  }

  // Anything else (500, 502, 503) is a problem on our side, like Qwen3 or
  // the search not being available.
  return {
    type: "error",
    message: "The policy service could not complete this request. Please try again.",
  };
}

// Used when we couldn't reach the backend at all.
export function makeConnectionErrorReply() {
  return {
    type: "error",
    message: "The policy service could not be reached. Please try again.",
  };
}
