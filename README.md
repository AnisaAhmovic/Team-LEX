# Team-LEX

## Policy DB Chatbot
Team-LEX is developing an AI-powered web application that enables users to access and understand La Trobe University policies through natural language questions. The application combines a React frontend with a Django REST backend and investigates the use of Retrieval-Augmented Generation (RAG) to provide accurate, context-aware and source-grounded responses from the University's official Policy Database.

The project aims to improve the accessibility of institutional policies, reduce the time required to locate and interpret policy information, and support consistent, policy-aligned decision-making for students, staff and administrators.

---

## Project Objectives
The objectives of Team-LEX are to:
- Develop an AI-powered chatbot capable of answering questions about La Trobe University policies.
- Ingest and index the University's Policy Database into a structured, searchable knowledge base.
- Investigate the use of Retrieval-Augmented Generation (RAG) to ensure responses are grounded in official policy documents.
- Provide source citations alongside chatbot responses where applicable.
- Develop a responsive web application using React and Django.
- Ensure responses are accurate, consistent and aligned with official university policies.
- Improve access to institutional knowledge while reducing administrative effort and policy misinterpretation.

---

## System Architecture
The proposed solution consists of the following major components:
- **React Frontend** providing the user interface.
- **Django Backend** exposing REST API endpoints.
- **REST API** enabling communication between the frontend and backend.
- **Retrieval Layer (RAG)** responsible for searching relevant policy content.
- **Large Language Model (LLM)** for generating natural language responses using retrieved context.
- **La Trobe University Policy Database** as the authoritative knowledge source.

---

## Project Scope
### Must Haves
- Secure ingestion and indexing of Policy Database documents.
- Vector-based search capability.
- Investigation and implementation of Retrieval-Augmented Generation (RAG) or a similar retrieval approach.
- Web-based chatbot interface.
- Policy citations and document references in responses.
- Audit logging of user interactions.
- Compliance disclaimer presented to users.

### Nice to Haves
- Role-based contextual responses for different user groups (e.g. students, academic staff and professional staff).
- Automatic generation of frequently asked questions from common queries.

### Optional
- Voice-enabled interaction.
- Role-based authentication and access control.

---

## Quality, Accuracy and Compliance
Quality, accuracy and compliance are fundamental design principles of Team-LEX.

The chatbot is designed to:
- Generate responses grounded in official La Trobe University policy documents.
- Reduce AI hallucinations through Retrieval-Augmented Generation (RAG).
- Provide policy references and supporting citations where appropriate.
- Avoid speculative or unsupported responses.
- Direct users to appropriate university contacts where official interpretation or clarification is required.
- Promote consistent, reliable and policy-compliant information across the university community.

The chatbot is intended to support policy discovery and understanding. It is not designed to replace official university advice or decision-making processes.

---

## Constraints and Limitations
The project operates under the following constraints:
- Responses must rely exclusively on authorised La Trobe University policy documents.
- AI-generated responses must not provide legal advice or information beyond documented policy interpretation.
- Policy ingestion and storage must comply with university copyright, governance and cybersecurity requirements.
- The knowledge base must be updated as policies are revised to maintain response accuracy.
- The system must prioritise reliability, transparency and traceability over response creativity.

---

## Technology Stack
### Frontend
- React
- JavaScript
- HTML
- CSS

### Backend
- Python
- Django
- Django REST Framework

### AI and Retrieval
- Retrieval-Augmented Generation (RAG)
- Large Language Models (LLMs)
- Vector Search

### Development Tools
- Git
- GitHub
- Visual Studio Code

---

## Repository Structure
```
Team-LEX/
├── api/
├── mysite/
├── manage.py
├── requirements.txt
├── .gitignore
├── README.md
└── .env (excluded from version control)
```

---

## Team
Team-LEX is a collaborative capstone project developed by a team of five students at La Trobe University. 

NOAH U.
SHARMANE V.
ANISA A.
KIRSTIN B.
JOSHUA F.

The project follows a collaborative software development approach, with team members contributing across system architecture, frontend development, backend development, API integration, AI and retrieval components, testing, documentation and project management.

This repository serves as the shared codebase for the design, development and evaluation of the Policy DB Chatbot.

---

## Licence
This repository has been developed for educational purposes as part of a university capstone project.

Policy documents remain the intellectual property of La Trobe University. AI-generated responses are intended to assist with policy interpretation and must always be considered alongside the official policy documentation.
