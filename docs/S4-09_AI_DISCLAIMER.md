# S4-09: AI disclaimer and responsible guidance

Task 9 adds a disclaimer to the Lex chat page that is always on screen. It
builds on Task 8 (S4-08), which added the fallback and error messages.

## Wording (draft, needs approval)

There was no approved disclaimer wording in the repo. The README only says a
"compliance disclaimer" must be shown and that responses "must not provide legal
advice". So this wording is a **draft** and needs to be checked by the team or
client before release.

> **AI-assisted, not legal advice.** Lex uses AI to help you find and understand
> La Trobe University policies, and it can make mistakes. The official policy is
> always the source of truth, so check the La Trobe Policy Library or contact the
> relevant University office.

How it covers what the task asks for:

| Requirement | Words that cover it |
| --- | --- |
| Lex gives AI-assisted policy information | "AI-assisted", "Lex uses AI to help you find and understand La Trobe University policies" |
| The University policy is the source of truth | "The official policy is always the source of truth", with a link to the Policy Library |
| Lex is policy access/interpretation, not legal advice | "not legal advice" |
| Responsible guidance | "check the La Trobe Policy Library or contact the relevant University office" |

To change the wording, edit `frontend/src/components/Disclaimer.jsx`. The checks in
`frontend/verify_disclaimer.mjs` will fail if any of the required points are removed.

## Where it goes and why

The disclaimer sits just above the question box, outside the list of messages.

- Only the message list scrolls. The header, disclaimer and question box stay put,
  so the disclaimer is visible before the first question and after every answer.
- It is right where people type, so they see it when they ask something.
- It is blue so it doesn't look like a fallback (amber) or an error (red).

Fallbacks still show their own "Open the La Trobe Policy Library" link from Task 8,
so the guidance is there even when there's no answer.

## Automated checks

Run from the `frontend` folder:

```
npm run test:disclaimer
```

1. Says the information is AI-assisted
2. Says it is not legal advice
3. Says the official policy is the source of truth and links to the Policy Library
4. Has an accessible label for screen readers
5. Is on the page before any question
6. Is outside the scrolling message list, so it can't scroll away
7. Fallbacks still keep their Policy Library link

## Browser testing (22 September 2026)

Tested with the real backend: Django, BGE-M3 and qwen3:4b through Ollama.

| Test | Result |
| --- | --- |
| Before any question | Pass. Disclaimer shown above the question box |
| After a supported answer (group assessment, "40% [S1]") | Pass. Still visible after the messages scrolled |
| After a fallback (Bundoora parking permit) | Pass. Still visible, and the fallback kept its own Policy Library link |
| After an error (Qwen3 failed to load) | Pass. Still visible |

Screen sizes:

| Size | Disclaimer height | Space left for messages | Text size | Fully on screen | Sideways scrolling |
| --- | --- | --- | --- | --- | --- |
| Desktop (chat window 900 x 700) | 2 lines (checked by screenshot, not measured) | Most of the window | 13.6 px | Yes | No |
| Tablet 768 x 1024 | 79 px | 421 px | 13.6 px | Yes | No |
| Phone 375 x 812 | 107 px | 490 px | 12.8 px | Yes | No |
| Small phone 360 x 640 | 107 px | 318 px | 12.8 px | Yes | No |

On the smallest phone the disclaimer takes up more space, but there is still
enough room for a question and an answer.

## Known limitations

- The wording is a draft until the team/client approves it.
- The disclaimer is always shown in full. It can't be collapsed, so it takes up
  more room on small phones.
- The first answer after the model has been idle can take close to the 60 second
  Qwen3 timeout on a laptop (also noted in Task 8).
