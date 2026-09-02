from engine.task.condition import Condition

class SynchronizationNotifier:
    def __init__(self) -> None:
        self.connect    = Condition("Connect")
        self.sync       = Condition("Sync")
        self.input      = Condition("Input")
        self.presentation = Condition("Presentation")

        self.should_exit_wait = False
        self.has_client_input = False

    def WhenInput(self):
        self.has_client_input = True
        self.input.NotifyAll()

    def WhenPresentation(self):
        self.presentation.NotifyAll()

    def NotifyAll(self):
        self.sync.NotifyAll()
        self.input.NotifyAll()
        self.presentation.NotifyAll()
        self.connect.NotifyAll()

    def ExitWait(self):
        self.should_exit_wait = True
        self.NotifyAll()

    def RefreshExitWait(self):
        self.should_exit_wait = False

