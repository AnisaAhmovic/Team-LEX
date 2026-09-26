function LexBotIcon({ className = "" }) {
  return (
    <svg
      className={`lex-bot-icon ${className}`}
      viewBox="0 0 48 48"
      role="img"
      aria-label="LEX AI assistant"
    >
      <line className="lex-bot-antenna" x1="24" y1="10" x2="24" y2="6" />
      <circle className="lex-bot-accent" cx="24" cy="4.5" r="3" />

      <rect
        className="lex-bot-head"
        x="8"
        y="11"
        width="32"
        height="27"
        rx="9"
      />

      <rect
        className="lex-bot-face"
        x="12"
        y="15"
        width="24"
        height="17"
        rx="6"
      />

      <circle className="lex-bot-eye" cx="19" cy="23" r="2.3" />
      <circle className="lex-bot-eye" cx="29" cy="23" r="2.3" />

      <path
        className="lex-bot-smile"
        d="M19 28 C21.5 30 26.5 30 29 28"
      />

      <rect className="lex-bot-ear" x="4.5" y="19" width="5" height="11" rx="2.5" />
      <rect className="lex-bot-ear" x="38.5" y="19" width="5" height="11" rx="2.5" />

      <path className="lex-bot-neck" d="M20 38 V42 H28 V38" />
      <path className="lex-bot-base" d="M16 44 H32" />
    </svg>
  );
}

export default LexBotIcon;
