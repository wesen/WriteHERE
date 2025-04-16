from enum import Enum


class TaskStatus(Enum):
    # Dependent nodes have not yet completed execution
    NOT_READY = 1
    # All dependent nodes have completed execution, can begin execution
    READY = 2
    # Needs to be updated through dependent nodes
    NEED_UPDATE = 3
    # All internal nodes have completed execution, needs to perform convergence operation
    FINAL_TO_FINISH = 4
    # Convergence operation completed, needs to perform post-verification reflection
    NEED_POST_REFLECT = 5
    # Planning - plan reflection - execution - post-verification reflection all completed and passed
    FINISH = 6
    # Planning completed
    PLAN_DONE = 7
    # Internal nodes in execution = Plan reflection completed
    DOING = 8
    # Task failed
    FAILED = 9


class NodeType(Enum):
    PLAN_NODE = 1
    EXECUTE_NODE = 2
