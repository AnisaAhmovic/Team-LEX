# Team LEX Branching Strategy

This document defines the Git workflow used for the Team LEX repository.

## Main branch

`main` is the shared integration branch. It should contain reviewed, working project code. Normal development work should not be committed directly to `main`.

## Working branches

Create a branch from the latest `main` for each piece of work.

Recommended prefixes:

- `feature/` for new functionality
- `fix/` for bug fixes
- `docs/` for documentation-only changes
- `chore/` for configuration, tooling and maintenance

Where a Jira work item exists, include its key in the branch name where practical.

Examples:

- `feature/COPL-131-lex-ai-chatbot-ui`
- `feature/COPL-140-policy-retrieval`
- `fix/COPL-145-citation-display`
- `docs/COPL-120-setup-guide`

## Pull request process

1. Pull the latest `main`.
2. Create a task-specific branch.
3. Make focused commits with clear messages.
4. Test the changed component locally.
5. Push the branch and open a pull request into `main`.
6. Describe what changed, how it was tested and any known limitations.
7. Record contribution attribution when integrating work originally completed by another team member.
8. Review the pull request before merging.
9. Prefer squash merge for small task branches unless preserving separate commits is useful.
10. Delete the working branch after the change is safely merged.

## Commit messages

Use short, action-based commit messages, for example:

- `Configure Django REST backend`
- `Add Lex AI frontend prototype`
- `Document local development setup`
- `Fix policy metadata parsing`

## Team rules

- Do not commit `.env`, local databases, `node_modules`, virtual environments or generated build output.
- Do not commit secrets or credentials.
- Keep pull requests focused on one logical change or Jira task where practical.
- Pull or rebase from the current `main` before final review if the branch has become outdated.
- Resolve merge conflicts on the working branch rather than directly on `main`.
- Use the pull request description and commit history as evidence of project contribution and review.
