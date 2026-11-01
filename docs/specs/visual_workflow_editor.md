# Once — Post-Recording Visual Workflow Editor



## 1. Objective



Redesign the post-recording experience in Once so that, after the user finishes recording a task and the AI analyzes it, the application presents the inferred steps as an interactive, connected visual workflow.



Use the supplied workflow-editor screenshot as the primary visual and interaction reference.



The desired interface resembles a modern visual automation editor: individual task cards are arranged on a large canvas, connected by lines that show execution order, with branches representing alternative outcomes. Selecting a card opens a contextual panel where the user can inspect and modify its details.



The most important addition is the ability to **insert steps, instructions, conditions, and alternative paths between existing steps**, allowing users to correct and refine the AI-generated workflow without starting over.



This is a UI and interaction-design specification. Do not redesign unrelated parts of Once or redefine its overall architecture.



## 2. Core User Experience



The intended experience is:



1. The user finishes recording a task.

2. Once analyzes the recording and identifies the meaningful actions.

3. Once presents the inferred workflow as connected nodes on a visual canvas.

4. The user inspects the sequence and corrects any inaccurate or incomplete steps.

5. The user can select any step to see its details.

6. The user can insert additional steps or written instructions between existing steps.

7. The user can create conditional branches for different outcomes.

8. The user can modify connections and reorganize the workflow visually.

9. The user can review the resulting workflow, save it, and use the existing execution functionality.



The interface should make the AI's interpretation easy to understand and correct.



**The user should not have to edit code or navigate a long list of configuration forms to refine the workflow. The workflow diagram itself should be the primary editing surface.**



---



## 3. Main Layout



Use a four-part layout inspired by the reference image.



### A. Left navigation sidebar



Keep the existing Once navigation structure and visual identity.



The sidebar may contain the existing sections, such as:



- Home

- Automations

- Files

- Activity

- Settings



Highlight the current section.



Do not unnecessarily redesign these sections. The focus of this task is the workflow editor.



### B. Top workflow header



The header should contain:



- Breadcrumb navigation.

- Editable workflow name.

- Workflow status.

- Undo.

- Redo.

- Test run.

- Save workflow.



Example:



`My automations / Prepare and verify an invoice`



The title can be edited inline.



The status might display `Draft`, `Needs review`, or `Ready to test`, depending on the actual workflow state.



If the AI has identified uncertain steps, show a concise indicator such as `2 steps need review`.



The Save button must save the workflow without running it.



Undo and Redo should reverse workflow-editing operations.



Test run should use the application's existing execution and safety mechanisms.



### C. Main workflow canvas



This is the largest region of the window.



It should occupy most of the available space and contain the connected workflow.



The canvas should support:



- Zooming in and out.

- Panning.

- Fit-to-screen.

- Selecting nodes.

- Moving nodes.

- Selecting connections.

- Inserting nodes between connected steps.

- Creating and editing branches.

- Displaying warnings and execution status.

- A minimap for larger workflows.



Use a subtle dotted grid, a light background, rounded cards, curved connectors, and restrained colors, following the supplied reference image.



The design should feel clean, professional, and approachable rather than overly technical.



### D. Right-side details inspector



Selecting a node should open a contextual inspector on the right.



The inspector displays the selected node's configuration and editing options.



It should remain part of the main window rather than opening a separate window for routine editing.



When no node is selected, the inspector may display a brief explanation of how to edit the workflow or show general workflow information.



The user should be able to close the inspector to give the canvas more room.



### E. Bottom canvas action bar



Provide a compact toolbar containing:



- `+ Add step`

- `+ Add decision`

- `+ Add note`



When the user selects a connection, expose an `Insert step` action.



The toolbar should also provide a short contextual hint when appropriate, such as:



`Select a connection to insert a step between existing actions.`



Avoid filling the interface with buttons that are only rarely used.



---



## 4. Connected Workflow Nodes



Represent each meaningful action as a distinct card.



A node should contain:



- An icon representing its category.

- A concise action name.

- An optional target or application name.

- A short summary of its configuration.

- Connection handles.

- An optional warning or state indicator.



Example workflow:



`Start`

→ `Open invoice folder`

→ `Select invoice`

→ `Open invoice application`

→ `Import invoice`

→ `Wait for extraction`

→ `Verify required fields`

→ `Save result`

→ `Finish`



The node labels should be short enough to scan quickly.



Longer descriptions belong in the details inspector.



### Node categories



Use visually distinct but consistent styles for:



- Start or trigger.

- Application interaction.

- Browser interaction.

- File operation.

- Wait.

- Verification.

- Decision.

- Manual review.

- Note.

- Finish.



Different categories may use different icons and subtle accent colors.



Avoid excessive color saturation. Nodes should remain visually consistent with the supplied screenshot.



### Connections



Connections should communicate the actual execution order.



Use curved lines with clearly visible connection points.



Arrows or another unambiguous directional indicator should make the direction of execution clear.



When the user selects a node, subtly highlight its incoming and outgoing connections.



When the user selects a connection, highlight it and make its insertion controls available.



Connections must represent real workflow relationships. Do not create decorative connections that have no corresponding execution meaning.



### Node selection



Clicking a node selects it and opens its details inspector.



The selected node should have a clear outline or highlight.



The canvas should not unnecessarily recenter or rearrange itself when a node is selected.



Moving a node should change its visual position without changing its execution semantics.



---



## 5. Inserting Steps Between Existing Steps



This is one of the most important requirements.



The user must be able to add a step in the middle of an existing workflow without rebuilding the diagram.



Suppose the workflow contains:



`Open folder → Select invoice`



The user wants to filter out non-PDF files before selecting an invoice.



They should be able to select the connection between the two nodes and choose:



`Insert step`



A contextual menu should display the available step types.



For example:



- Application action.

- Browser action.

- File operation.

- Wait.

- Verification.

- Decision.

- Manual review.

- Note.



Only actions supported by the existing application should be offered as executable operations.



After the user chooses a step, the application should insert it into the connection automatically.



The resulting workflow becomes:



`Open folder → Filter files → Select invoice`



The original connection should be replaced with the necessary new connections.



The downstream workflow must remain intact.



The new node should appear at a sensible position on the canvas.



The user should not have to manually reconnect every downstream node.



### Insertion interaction



Support the following interaction:



1. The user clicks a connection.

2. The connection becomes highlighted.

3. An insertion control appears near the selected connection.

4. The user clicks `+` or `Insert step`.

5. A compact menu appears.

6. The user chooses a step type.

7. The new node is inserted.

8. The details inspector opens for the new node.

9. The user configures the new operation.



The same functionality may also be available through a right-click context menu.



### Inserting multiple steps



The user should be able to repeat this operation to insert multiple consecutive steps.



For example:



`Open folder → Filter files → Sort by date → Select newest invoice`



The interface should preserve the order and relationships of the existing workflow.



### Undo



Insertion must be reversible.



Undoing an insertion should restore the original connection and remove the inserted node from the workflow definition.



It must not execute or reverse external actions.



---



## 6. Adding Notes and Instructions Between Steps



The user should be able to add explanatory information to the workflow without necessarily creating an executable operation.



For example:



`Open invoice folder`



↓



**Note: Ignore invoices that have already been processed.**



↓



`Select newest invoice`



Provide a dedicated `Add note` action.



A note should have:



- Editable text.

- A clear visual distinction from executable nodes.

- A compact appearance on the canvas.

- The ability to be moved or deleted.

- A way to edit its content.

- Normal Undo and Redo support.



Notes are documentation. They should not automatically become executable instructions.



### Natural-language instructions



In addition to ordinary notes, allow users to provide instructions that affect a particular step.



For example, the user selects `Select invoice` and adds:



`Only consider PDF files created during the last seven days.`



The UI should distinguish between:



1. **Note:** Information for the user.

2. **Step instruction:** A proposed change to the behavior of an operation.



A step instruction should be interpreted into supported, structured configuration.



For example, the instruction above might result in a file-filter configuration.



The application should show the proposed change before accepting it.



If the instruction cannot be represented by a supported operation, display a clear explanation instead of pretending that the workflow has changed.



Do not allow arbitrary natural-language text to bypass the existing validation or execution rules.



---



## 7. Creating Alternative Paths and Decisions



The editor should allow users to create branching workflows.



A decision node evaluates a condition and directs execution to the appropriate path.



Example:



`Verify required fields`

→ `Are all fields correct?`



The decision has two outgoing branches:



- `Yes` → `Save result`

- `No` → `Review extracted fields`



The branches can subsequently converge at a shared `Finish` node, provided the execution engine supports the corresponding graph semantics.



### Adding a decision



The user clicks `Add decision`.



The application creates a decision node that can be connected to the appropriate steps.



Alternatively, the user can select an existing connection and insert a decision directly into it.



The inspector should let the user configure:



- Decision name.

- Condition.

- Relevant input or output.

- Supported comparison.

- Branch labels.

- What happens if the condition cannot be evaluated.



The condition should use structured, validated configuration.



Do not imply that a decision is functional merely because two outgoing connections are visible.



### Editing branches



Users should be able to:



- Add an outgoing branch when the decision type supports it.

- Rename branch labels.

- Connect branches to existing nodes.

- Create a new step on a branch.

- Move nodes within a branch.

- Reconnect a branch.

- Delete a branch when doing so leaves a valid workflow.

- Merge paths where the workflow engine supports it.



When the user deletes or disconnects a branch, explain any resulting invalid workflow structure.



### Branch visualization



Place alternative paths above or below the main path.



Label connections clearly, such as `Yes`, `No`, `Success`, or `Failure`.



Use distinct but restrained connector styling.



The layout should make it immediately obvious which operations belong to each path.



### Important distinction



A conditional branch is not the same as parallel execution.



The interface should not treat multiple outgoing decision paths as operations that all execute.



Likewise, multiple incoming connections must not automatically imply a synchronization point unless that behavior is explicitly supported.



The editor must reflect the execution semantics implemented by the underlying engine.



---



## 8. Step Details Inspector



The inspector should change according to the selected node.



A typical inspector contains:



### Header



- Node icon.

- Step name.

- Action category.

- Optional overflow menu.

- Close button.



### Common fields



- Editable step name.

- Action-specific target.

- Action configuration.

- Optional timeout.

- Failure behavior, where supported.

- Safety or permission information.

- Advanced settings, when needed.



### Examples



For an application action, the inspector might display:



- Application.

- Target window.

- Control or element.

- Action to perform.

- Timeout.



For a file operation, it might display:



- Authorized folder.

- File-selection criteria.

- File type.

- Sorting or filtering rules.



For a verification step, it might display:



- Target result.

- Conditions to verify.

- Expected values.

- Timeout.

- Failure behavior.



For a decision, it might display:



- Condition.

- Inputs.

- Comparison.

- Outgoing branches.



These are examples. The actual fields must correspond to supported operations.



### Safety information



The inspector should clearly identify whether the operation is read-only or mutating.



If approval is required for a mutating operation, communicate this accurately.



The UI must not bypass or independently replace the existing approval gate.



### Editing feedback



Configuration changes should update the node's summary when relevant.



Invalid values should produce clear inline feedback.



The user should be able to cancel or undo an editing operation.



Routine changes should not require modal dialogs.



---



## 9. Reviewing AI-Generated Steps



The editor should communicate that the initial workflow was inferred from a recording.



It should also distinguish between steps that the AI confidently identified and steps that require user review.



A small information banner above the canvas could display:



`Generated from your recording · 2 items need review`



Provide an action such as `View recording` if the original recording is available.



Clicking a review indicator should take the user to the relevant node.



### Review states



A node may require review because:



- The target application or control was ambiguous.

- The recording did not establish the intended condition.

- An important parameter could not be inferred.

- A step was inferred from uncertain evidence.

- A necessary operation appears to be missing.



The user should be able to identify and correct these issues directly in the editor.



Do not invent confidence scores or claim that the AI verified an action if it only inferred the action from the recording.



The editor should show only review information supported by the actual analysis results.



### Incomplete configuration



If the AI recognizes an action but cannot determine the target, the node should still be editable.



For example:



`Click button`



`Target needs review`



Selecting the node should explain what information is missing.



The workflow may be saved as a draft, but it should not be treated as ready to execute if a required target is unresolved.



---



## 10. Execution and Test-Run Feedback



Although the main task is UI redesign, the editor should be prepared to display execution state.



During a run, nodes should visibly reflect their current status.



For example:



- Completed steps receive a subtle success indicator.

- The current step is highlighted.

- Failed steps display an error indicator.

- Skipped steps appear visually subdued.

- A paused step indicates that user input is required.



The UI should display actual execution events from the existing engine rather than simulate progress.



If a step fails, the user should be able to select it and inspect the error or available evidence.



A failed run should not make the saved workflow impossible to edit.



Execution results should remain distinct from the workflow's saved configuration.



Do not change the underlying execution engine merely to produce visual effects.



---



## 11. Context Menus and Editing Shortcuts



Provide contextual menus to reduce unnecessary navigation.



### Node context menu



Possible actions:



- Edit details.

- Add step after.

- Insert step before.

- Add note.

- Add decision.

- Duplicate step, if safe and supported.

- Delete step.

- Disconnect or reconnect.

- Undo, where applicable.



### Connection context menu



Possible actions:



- Insert step.

- Insert decision.

- Add note.

- Disconnect.

- Delete connection, if appropriate.



The exact actions should depend on the selected object.



Keyboard shortcuts may be introduced for common operations such as Undo, Redo, Delete, and Save.



Shortcuts must not conflict with text entry in inspector fields.



### Drag-and-drop



Where practical, allow the user to drag a step from the bottom toolbar onto the canvas or onto an existing connection.



Dropping onto a connection should insert the step into that connection.



Dropping onto an empty canvas should create an unconnected node or start a clearly defined connection interaction.



Do not create unexpected connections based solely on approximate visual proximity.



---



## 12. Visual Design Guidelines



Use the supplied screenshot as the primary design reference.



### Overall appearance



- Clean, modern desktop UI.

- Light background.

- Subtle dotted-grid canvas.

- White or lightly tinted cards.

- Thin, curved connectors.

- Rounded corners.

- Restrained shadows.

- Clear typography.

- Consistent spacing.

- Minimal visual clutter.



### Color usage



Use subtle category accents rather than large saturated backgrounds.



Selected nodes should have a visible blue or equivalent accent outline.



Warnings should be noticeable without making the entire workflow look like an error state.



Use text and icons in addition to colors.



### Node sizing



Cards should be large enough to show an icon, readable title, and short summary.



Long titles should wrap or truncate gracefully.



The full configuration should remain in the inspector rather than being squeezed into the card.



### Responsive layout



The editor should remain usable at different window sizes.



When the window becomes narrower:



- The canvas should retain as much space as possible.

- The inspector may become narrower or collapsible.

- The node layout should remain navigable.

- Essential controls should remain accessible.



The application should not require an excessively wide monitor to use the editor.



### Accessibility



Ensure readable text, visible focus indicators, keyboard-accessible controls, and sufficient contrast.



Do not rely on color alone to communicate errors, branch outcomes, or execution status.



---



## 13. Workflow Validation in the UI



The editor should display meaningful validation feedback.



Examples include:



- A required target is missing.

- A node has an invalid configuration.

- A decision is missing an outgoing branch.

- A connection references a nonexistent node.

- A required step is unreachable.

- A workflow contains an unsupported cycle.

- A step uses an unsupported operation.

- A connection has incompatible endpoints.



The UI should distinguish between warnings and blocking errors.



Warnings may allow the workflow to be saved as a draft.



Blocking errors should prevent execution when the workflow is invalid.



Provide a way to navigate from a validation message to the affected node or connection.



Validation must apply to the workflow as a whole, not only to individual node forms.



The visual editor must not become an alternate path that bypasses existing schema validation, execution policy, or approval requirements.



---



## 14. Saving and Reopening



The visual representation should persist across sessions.



Saving a workflow should preserve:



- Nodes.

- Node configuration.

- Connections.

- Decision conditions.

- Branch labels.

- Notes.

- Node positions.

- Relevant workflow metadata.



Reopening a workflow should restore its diagram in a predictable layout.



The application should distinguish between:



- Saved workflow configuration.

- Unsaved editing changes.

- Execution history.

- Current execution state.



If the user attempts to leave with unsaved changes, offer an appropriate warning or recovery option.



Do not store the visual graph separately in a way that allows it to disagree with the executable workflow definition.



The editor and execution engine must use one consistent workflow representation or a reliable, validated mapping between them.



---



## 15. Interaction Example



Consider a recorded task that imports an invoice and saves the extracted result.



Once initially generates:



`Start`

→ `Open invoice folder`

→ `Select invoice`

→ `Open invoice application`

→ `Import invoice`

→ `Wait for extraction`

→ `Verify required fields`

→ `Save result`

→ `Finish`



The user notices three problems.



First, the newest file may not be an invoice.



The user selects the connection between `Open invoice folder` and `Select invoice`, clicks `Insert step`, and adds `Filter PDF invoices`.



Second, the application sometimes takes longer to extract the invoice.



The user selects `Wait for extraction` and adjusts its timeout in the inspector.



Third, some invoices have missing or incorrectly extracted fields.



The user inserts a decision after `Verify required fields`:



`Are all required fields valid?`



The user connects the Yes branch to `Save result` and the No branch to `Review extracted fields`.



The final graph becomes:



`Start`

→ `Open invoice folder`

→ `Filter PDF invoices`

→ `Select invoice`

→ `Open invoice application`

→ `Import invoice`

→ `Wait for extraction`

→ `Verify required fields`

→ `Are all required fields valid?`



From the decision:



- **Yes** → `Save result`

- **No** → `Review extracted fields`



Both paths can reach `Finish` if the engine supports the required graph behavior.



The user can now understand, modify, and review the automation visually without rewriting it.



This is the intended experience.



---



## 16. Scope and Implementation Constraints



This specification describes the desired interface and user interactions. It does not imply that every operation shown in the examples already exists in Once.



Implementation must respect these constraints:



1. Preserve the existing native PySide6 application.

2. Integrate with the current workflow model and services.

3. Reuse supported operations instead of inventing duplicate action systems.

4. Keep the UI separate from execution-policy decisions.

5. Preserve the existing approval gate for mutating actions.

6. Do not claim unsupported actions are executable.

7. Do not silently change execution semantics when editing connections.

8. Do not discard user changes when rearranging the graph.

9. Keep saved workflows compatible with the existing persistence system wherever possible.

10. Do not redesign unrelated pages.

11. Do not switch the application's default entry point as part of this UI task unless explicitly authorized.

12. Do not introduce paid services merely to render or edit the workflow.



If a visual interaction requires unsupported backend functionality, make the limitation clear and identify the missing dependency. Do not create a convincing-looking control that silently does nothing.



---



## 17. Suggested Implementation Priorities



To keep the change manageable, implement the interface in stages.



### Priority 1: Workflow canvas



- Display existing workflow steps as connected nodes.

- Support selection.

- Add the details inspector.

- Add zoom, pan, and fit-to-screen.

- Preserve the existing workflow definition.

- Restore saved node positions.



### Priority 2: Basic editing



- Edit step names and supported configuration.

- Add a step.

- Delete a step safely.

- Insert a step into an existing connection.

- Add and edit notes.

- Support Undo and Redo.



### Priority 3: Branching



- Add decision nodes.

- Edit conditions supported by the engine.

- Label outgoing branches.

- Connect branches to existing or new steps.

- Validate the graph.

- Display branch-specific warnings.



### Priority 4: AI-generated workflow review



- Display the workflow's recording provenance.

- Highlight steps requiring review.

- Navigate directly to unresolved steps.

- Show proposed changes before applying them.

- Make uncertainty and unsupported operations clear.



### Priority 5: Execution feedback



- Display real execution states.

- Show errors and relevant evidence.

- Distinguish saved configuration from run results.

- Preserve the ability to edit the workflow after a failed run.



Priorities are a suggested implementation sequence, not permission to remove existing capabilities.



---



## 18. Acceptance Criteria



The redesign should be considered successful when:



1. The post-recording workflow appears as a connected diagram rather than only a list.

2. Each supported action has a readable node.

3. Selecting a node opens its contextual inspector.

4. Editing supported properties updates the workflow definition.

5. The user can insert a step into an existing connection.

6. Inserting a step preserves the surrounding workflow.

7. The user can add, edit, and remove explanatory notes.

8. The user can add a decision when the engine supports it.

9. Branches have clear labels and accurate execution semantics.

10. Invalid graph structures produce understandable feedback.

11. The canvas supports zooming, panning, and fit-to-screen.

12. Saved node positions and graph structure persist when reopening a workflow.

13. Undo and Redo work for supported editing operations.

14. Unsaved changes are handled safely.

15. The UI distinguishes AI-generated uncertainty from verified execution results.

16. Mutating actions continue to use the existing approval mechanism.

17. Unsupported operations are never presented as successfully executable.

18. The application remains responsive during editing.

19. Existing workflows continue to open correctly.

20. Existing navigation and unrelated application pages remain functional.



The final result should make Once feel like an approachable, visual automation editor: the AI creates the initial workflow, and the user can refine it by interacting directly with the diagram.

