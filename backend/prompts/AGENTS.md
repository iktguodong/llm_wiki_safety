# Anniu Wiki Rules

This wiki is the structured knowledge layer for the Anniu enterprise safety assistant.
Its purpose is to turn uploaded safety documents into a small, high-quality wiki that works well for question answering and document retrieval.

## Domain

- Primary domain: enterprise safety, emergency response, operations, compliance, training, and document management.
- Write for safety managers, compliance staff, and operations personnel.
- Prefer clear Chinese and practical language.
- Avoid software-development-centric wording unless the source document is actually about software.

## Ingest workflow

When a new source document is ingested, build the wiki in a way that makes future Q&A easier.

1. Read the whole source carefully.
2. Identify the document's main theme, key procedures, roles, risks, thresholds, and exceptions.
3. Create one summary page for the source document.
4. Create only the concept pages that are genuinely useful for search and question answering.
5. Link related pages with `[[wiki-links]]`.
6. Update `wiki/index.md` so the pages are easy to discover.
7. Append a clear entry to `wiki/log.md`.

Do not over-split content. Prefer a small set of strong pages over many thin pages.

## Output contract

Return only a valid JSON array.
Do not add explanations, markdown fences, or extra commentary outside the JSON.

Each item must have:

```json
{
  "file": "wiki/page-name.md",
  "content": "# Page Title\n\n**Summary**: ...\n\n**Sources**: ...\n\n**Last updated**: YYYY-MM-DD\n\n---\n\n..."
}
```

## Page selection

- Create a summary page for the source document.
- Create concept pages only for major ideas that users are likely to ask about later.
- Good concept pages usually cover one of these:
  - a procedure
  - an emergency response stage
  - a role or responsibility
  - a risk type
  - a threshold, condition, or trigger
  - a checklist or operating rule
- If a topic is small or only mentioned once, keep it inside a broader page instead of creating a separate file.
- Avoid creating pages for `index.md` and `log.md`.

## Page writing style

Every page should be written so it is easy to answer questions from later.

- Use a short, clear title that matches how users would search for it.
- Put the most important definition or conclusion near the top.
- Use headings for structure, but keep the page concise.
- Prefer bullets, steps, and tables when they improve scanning.
- Use plain language and avoid vague generalities.
- If a page describes a process, write it in the order users would perform it.
- If a page describes a role, include what the role does, when it acts, and what it coordinates with.
- If a page describes a risk or incident, include common triggers, symptoms, immediate actions, and escalation conditions.

## Sources and traceability

- Every page must include a `Sources` section.
- Each page should cite the raw document file it is based on.
- If a statement is not clearly supported by the source, mark it as uncertain or omit it.
- Do not invent facts, thresholds, phone numbers, timelines, or responsibilities.
- If multiple source documents disagree, note the difference explicitly instead of forcing a single answer.

## Wiki links

- Use `[[wiki-links]]` only inside a dedicated `## 相关页面` (Related pages) section at the bottom of a page.
- Every `[[xxx]]` must point to a page slug that is actually being created in the same ingest run, or that already exists in the wiki. **Never invent slugs.**
- Do not put `[[xxx]]` inside body paragraphs, headings, tables, or lists. Use plain text for in-line concept mentions.
- If there are no good related pages, omit the `## 相关页面` section entirely instead of writing speculative links.
- Keep links purposeful and few. A page rarely needs more than 3-5 outbound links.

## Citation rules

- Every factual claim should reference its source document.
- Use `（来源：原文档名）` after the claim to cite the raw file (use the actual filename associated with the page).
- If multiple sources disagree, note the difference explicitly instead of forcing a single answer.
- If a claim has no source in the supplied materials, mark it as uncertain (“不足以从当前文档直接确认”) or omit it. Do not invent sources, thresholds, phone numbers, timelines, or responsibilities.

## Index and log

- Update `wiki/index.md` after creating or changing pages.
- Update `wiki/log.md` with the source name, date, and the pages that changed.
- Keep the index concise and useful for navigation.

## Answerability rules

The wiki should be optimized for future questions.

- Favor question-friendly page names and titles.
- Keep one page focused on one question or one concept cluster.
- Write in a way that makes retrieval and summarization easier.
- Include the exact terms that a user would likely ask about.
- Add cross-links between procedure pages, role pages, and incident pages.
- If a document contains multiple independent topics, split them only where it improves search and answer quality.

## Quality checks

Before finalizing the wiki content:

- Check that the summary page captures the source document's main purpose.
- Check that concept pages are complete enough to answer common questions.
- Check that the page structure is consistent across files.
- Check that links, titles, and sources are coherent.
- If uncertain, choose the simpler and more useful structure.
