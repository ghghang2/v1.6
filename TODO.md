# General Work Instructions That Holds True for Every Item Listed Below
Complete every item in this list to the best of your abilities. 
Create a new progress tracker file for each task. Never start or end an item on this list before updating the item's progress tracker.
If you run into a road block that you absolutely cannot solve, note the blocker in the progress tracker for the item and move on.
Very important note (since we have very limited context window and we are running on unstable servers):
- You are required to periodically update the progress tracker.
- You are required to periodically push to git.
- You are required to notify the team of your work progress using send_email tool upon completion or before moving on to another item on this list.

## SOTA Autonomous Agent Review (Pending)
Code Review Phase:
Review the code in our project repository (nbchat/ folder). Our project objective is to build the most capable SOTA autonomous agent. A previous analyst created the SOTA_Autonomous_Agent_Review.md and SOTA_Review_Progress_v2.md documentation, review it with a critical eye. A lot of files have changed since these documentation was created. So inevitably changes will need to be made. 

Research and Planning Phase:
In order to be informed of the latest SOTA, review the openclaw project repository. Review any and all projects you can find that implement autonomous agents. Think carefully about what we can learn from these SOTA projects and compile concepts and ideas we should refactor into our project. Update the documents with your findings and thoughts. Consider ease of refactoring and level of impact. We want to implement based on best bang-for-our-buck. Update your plan into the documentation

Implementation Phase:
After you have completed the research and planning phase. Begin implementation. Notify of completion once you are done via send_email. Don't for get to push to git periodically as to not lose progress.

## Agent Memory Testing (In Progress)
Completed:
- [x] Created technical documentation for context management (nbchat/core/context_management_technical_doc.md)
- [x] Created unit tests for context manager importance scoring (nbchat/ui/test_context_manager.py) - 8 tests passing
- [x] Created unit tests for database operations (nbchat/core/test_db.py) - 21 tests passing

Next Steps:
- [ ] Assess gap between agent_memory_report.docx and current implementation
- [ ] Review additional failure modes in context management
- [ ] Complete any remaining test coverage

## Agent Memory Report Implementation (In Progress)
Completed:
- [x] Review current implementation of context management
- [x] Review agent_memory_report.docx
- [x] Identify gaps between report and implementation
- [x] Create technical documentation for context management

Next Steps:
- [ ] Implement recommended improvements from the report
- [ ] Address identified gaps
- [ ] Verify improvements with additional tests

## Progress Tracking Files Created:
- Agent_Memory_Testing_Progress.md
- SOTA_Agent_Review_Progress.md
- nbchat/core/Agent_Memory_Testing_Progress.md
- nbchat/core/context_management_technical_doc.md
- SOTA_Agent_Review.md
- SOTA_Review_Progress_v2.md
- Agent_Memory_Report_Implementation_Progress.md
- nbchat/ui/test_context_manager.py
- nbchat/core/test_db.py
