# Reproducible prototype demonstration

This is a manual checklist, not a claim that live validation was completed.
Use text PDFs you have permission to share with Groq and record model/configuration,
corpus version, document/page counts, and the date of the run.

1. Start from the documented setup. Record initial indexing duration.
2. Ask a specific question with an answer on a known page. Compare the answer
   against the actual PDF and the retrieved source panel; inspect inline IDs.
3. Ask a pronoun follow-up and verify relevant evidence is retrieved. Ask `It?`
   after discussing multiple items and confirm clarification rather than guessing.
4. Ask a question absent from the collection. Verify refusal or mark a failure;
   a relevance threshold alone does not guarantee safe refusals.
5. Change Top K and ask another question. Confirm logs do not show a rebuild
   when files/configuration have not changed; prior answer evidence remains visible.
6. Restart. Confirm the saved index loads without re-embedding unchanged PDFs.
7. Change a PDF or chunk setting. Confirm rebuilding and updated evidence.
8. Stop Ollama and force refresh. Verify safe recovery text without a raw traceback.
9. Record a short screen capture showing answer, evidence, refusal, follow-up,
   and unchanged restart. Do not record API keys or confidential document content.

For a real evaluation, prepare approximately 20–30 manually reviewed questions
covering standalone answers, multi-source answers, follow-ups, ambiguity, and
unsupported questions. Record expected document/page evidence and assess answers
for factual support separately from retrieval scores. Publish observed results,
including failures. The existing five-case offline fixture does not substitute
for this evaluation.
