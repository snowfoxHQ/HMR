"""
HMR v1 - Complete Usage Example
Demonstrates the full cognitive runtime lifecycle
"""

from hmr import HMR, MemoryObject, RuntimeState


def example_scheduler_design_session():
    """
    Example: Multi-day Scheduler design project
    
    Demonstrates:
    - Memory ingestion
    - Runtime state persistence
    - Cross-session continuity
    - Active recall
    """
    
    print("=" * 70)
    print("DAY 1: Starting Scheduler Design")
    print("=" * 70)
    
    # Initialize HMR
    hmr = HMR(storage_path="./scheduler_project_hmr")
    
    # ========================================================================
    # PHASE 1: Initial Research
    # ========================================================================
    
    print("\n[Phase 1] Researching IPC protocols...")
    
    # Ingest research findings
    ipc_memory = hmr.ingest(
        content="""
        IPC Protocol Design Findings:
        - Async message passing is preferred over sync
        - Need reliable delivery guarantees
        - Should support priority queues
        - Must handle backpressure
        """,
        memory_type="concept",
        title="IPC Protocol Requirements",
        metadata={
            "tags": ["ipc", "scheduler", "architecture"],
            "runtime_dependencies": ["Scheduler Design"]
        }
    )
    
    print(f"  ✓ Stored: {ipc_memory.title} [{ipc_memory.id}]")
    
    # Record a failed approach
    failed_attempt = hmr.ingest(
        content="""
        Attempted: Simple thread-based scheduler
        Result: FAILED
        Reason: Deadlocks under high load
        Learning: Need async-first design
        """,
        memory_type="execution",
        title="Failed Attempt: Thread-based Scheduler",
        metadata={
            "tags": ["scheduler", "failure", "learning"],
            "confidence": 0.3
        }
    )
    
    print(f"  ✓ Recorded failure: {failed_attempt.title}")
    
    # Save runtime state at end of day
    print("\n[End of Day 1] Saving runtime state...")
    
    runtime_state = hmr.save_runtime_state(
        goal="Design async-first Scheduler architecture",
        plan=[
            "Research IPC protocols ✓",
            "Design Scheduler API",
            "Implement prototype",
            "Test under load"
        ],
        context={
            "current_focus": "architecture design",
            "blockers": ["Need to finalize IPC protocol"],
            "confidence": 0.6
        }
    )
    
    print(f"  ✓ Runtime state saved: {runtime_state.runtime_id}")
    print(f"  ✓ Active goal: {runtime_state.active_goal}")
    
    # Create system snapshot
    snapshot = hmr.snapshot()
    print(f"  ✓ System snapshot created")
    
    print("\n[Day 1 Complete] System shutdown...\n")
    
    # ========================================================================
    # SIMULATE SYSTEM RESTART (days later)
    # ========================================================================
    
    print("=" * 70)
    print("DAY 3: Resuming work (2 days later)")
    print("=" * 70)
    
    # Create new HMR instance (simulating restart)
    hmr2 = HMR(storage_path="./scheduler_project_hmr")
    
    # Restore runtime state
    print("\n[Restoration] Loading previous runtime state...")
    
    restored_state = hmr2.restore_runtime_state()
    
    print(f"  ✓ Runtime restored: {restored_state.runtime_id}")
    print(f"  ✓ Continuing goal: {restored_state.active_goal}")
    print(f"  ✓ Plan status:")
    for i, step in enumerate(restored_state.current_plan, 1):
        print(f"      {i}. {step}")
    
    # Active Recall automatically preloads relevant memories
    print("\n[Active Recall] System predicting needed memories...")
    
    recall_result = hmr2.recall(
        query="Scheduler design",
        context=restored_state.current_context,
        top_k=5
    )
    
    print(f"  ✓ Reasoning: {recall_result.recall_reasoning}")
    print(f"  ✓ Preloaded memories:")
    for mem in recall_result.memory_objects:
        score = recall_result.relevance_scores.get(mem.id, 0)
        print(f"      - {mem.title} (relevance: {score:.2f})")
    
    # ========================================================================
    # PHASE 2: Continue Design
    # ========================================================================
    
    print("\n[Phase 2] Continuing with Scheduler API design...")
    
    # Agent can now work with full context restored
    api_design = hmr2.ingest(
        content="""
        Scheduler API Design:
        
        class Scheduler:
            async def schedule(task: Task, priority: int)
            async def execute(task_id: str)
            async def cancel(task_id: str)
            
        Features:
        - Priority-based execution
        - Async-first API
        - Cancellation support
        """,
        memory_type="decision",
        title="Scheduler API Design v1",
        metadata={
            "tags": ["scheduler", "api", "design"],
            "runtime_dependencies": ["IPC Protocol Requirements"]
        }
    )
    
    print(f"  ✓ Stored: {api_design.title}")
    
    # Update runtime state
    hmr2.save_runtime_state(
        goal="Design async-first Scheduler architecture",
        plan=[
            "Research IPC protocols ✓",
            "Design Scheduler API ✓",
            "Implement prototype",
            "Test under load"
        ],
        context={
            "current_focus": "implementation",
            "completed": ["IPC research", "API design"],
            "confidence": 0.8
        }
    )
    
    print(f"  ✓ Runtime state updated")
    
    print("\n[Day 3 Complete]\n")
    
    # ========================================================================
    # DEMONSTRATION: Query with Active Recall
    # ========================================================================
    
    print("=" * 70)
    print("DEMONSTRATION: Active Recall Intelligence")
    print("=" * 70)
    
    print("\nScenario: Agent asks 'What IPC patterns should I use?'")
    print("  (Agent hasn't explicitly mentioned Scheduler)")
    
    result = hmr2.recall(
        query="IPC patterns",
        top_k=3
    )
    
    print("\nActive Recall prediction:")
    print(f"  Predicted needs: {', '.join(result.predicted_need)}")
    print(f"\n  Retrieved memories:")
    for mem in result.memory_objects:
        print(f"    - {mem.title}")
        print(f"      Type: {mem.type}")
        print(f"      Relevance: {result.relevance_scores[mem.id]:.2f}")
    
    print("\n  → Notice: System automatically linked IPC query to")
    print("           Scheduler context, even without explicit mention")
    
    print("\n" + "=" * 70)
    print("Example complete!")
    print("=" * 70)
    
    return hmr2


def example_agent_workspace():
    """
    Example: Multiple agents with separate workspaces
    """
    
    print("\n" + "=" * 70)
    print("MULTI-AGENT WORKSPACE EXAMPLE")
    print("=" * 70)
    
    hmr = HMR(storage_path="./multi_agent_hmr")
    
    # Agent 1: Frontend developer
    print("\n[Agent: Frontend] Creating workspace...")
    frontend_ws = hmr.get_workspace("agent_frontend")
    
    frontend_ws.active_goal = "Build user dashboard"
    frontend_ws.push_task({
        "name": "Design dashboard layout",
        "status": "in_progress"
    })
    
    # Store agent-specific memory
    hmr.ingest(
        content="Dashboard should use shadcn/ui components",
        memory_type="agent_memory",
        title="Frontend: Dashboard Design Decision",
        metadata={"tags": ["frontend", "ui"]}
    )
    
    print(f"  ✓ Workspace created: {frontend_ws.agent_id}")
    print(f"  ✓ Active goal: {frontend_ws.active_goal}")
    
    # Agent 2: Backend developer
    print("\n[Agent: Backend] Creating workspace...")
    backend_ws = hmr.get_workspace("agent_backend")
    
    backend_ws.active_goal = "Implement API endpoints"
    backend_ws.push_task({
        "name": "Design REST API",
        "status": "in_progress"
    })
    
    hmr.ingest(
        content="API should use FastAPI with async handlers",
        memory_type="agent_memory",
        title="Backend: API Framework Decision",
        metadata={"tags": ["backend", "api"]}
    )
    
    print(f"  ✓ Workspace created: {backend_ws.agent_id}")
    print(f"  ✓ Active goal: {backend_ws.active_goal}")
    
    # Save system state
    print("\n[System] Saving multi-agent state...")
    snapshot = hmr.snapshot()
    
    print(f"  ✓ Workspaces: {len(snapshot['workspaces'])}")
    for agent_id in snapshot['workspaces']:
        print(f"      - {agent_id}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Run examples
    hmr = example_scheduler_design_session()
    
    print("\n\n")
    
    example_agent_workspace()
    
    print("\n\n🎉 HMR v1 Examples Complete!\n")
