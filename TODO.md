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

## Agent Memory Testing (Pending)
Review our current implementation of context management by going to ubchat/ui/ folder and reviewing relevant files. Next, review agent_memory_report.docx report. Assess the gap between the report and our current implementation. If an idea does not make sense, make note of it. If an idea is great, also make a note of it! After reviewing, I want you to write a detailed technical documentation detailing our existing context management approach. After you finish creating the documentation, create tests to ensure our implementation covers all potential failure modes and are robust from them.