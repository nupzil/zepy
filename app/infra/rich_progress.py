import time

from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, SpinnerColumn, ProgressColumn, TaskID, \
    TransferSpeedColumn


class CustomSpinnerColumn(SpinnerColumn):
    def render(self, task):
        if task.fields.get("failed", False):
            return "[red] ✗[/red]"
        return super().render(task)


# 自定义时间显示列
class CustomTimeColumn(ProgressColumn):
    def __init__(self, show_remaining=True):
        super().__init__()
        self.show_remaining = show_remaining
        self.max_refresh = 0.1

    def render(self, task):
        """渲染时间信息"""
        elapsed = task.finished_time if task.finished else task.fields.get("_elapsed", task.elapsed)
        remaining = task.time_remaining
        if elapsed is None:
            return Text("")

        # 格式化已用时间（时:分:秒），省略为0的部分
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)

        elapsed_parts = []
        if hours > 0:
            elapsed_parts.append(f"{int(hours)}h")
        if minutes > 0 or hours > 0:
            elapsed_parts.append(f"{int(minutes)}m")
        elapsed_parts.append(f"{seconds:.2f}s")

        elapsed_text = " ".join(elapsed_parts)

        # 如果任务已完成，只显示总用时
        if task.finished:
            return Text.from_markup(f"[grey50]ET: [/grey50][blue]{elapsed_text}[/blue]")

        # 如果任务失败，显示红色用时
        if task.fields.get("failed", False):
            if task.fields.get("_elapsed", None) is None:
                task.fields["_elapsed"] = elapsed
            return Text.from_markup(f"[grey50]ET: [/grey50][red]{elapsed_text}[/red]")

        # 如果有预估剩余时间，显示ETA
        if remaining is not None and self.show_remaining:
            # 格式化预估剩余时间，省略为0的部分
            eta_hours, eta_remainder = divmod(remaining, 3600)
            eta_minutes, eta_seconds = divmod(eta_remainder, 60)

            eta_parts = []
            if eta_hours > 0:
                eta_parts.append(f"{int(eta_hours):02d}h")
            if eta_minutes > 0 or eta_hours > 0:
                eta_parts.append(f"{int(eta_minutes):02d}m")
            eta_parts.append(f"{eta_seconds}s")

            eta_text = "".join(eta_parts)
            return Text.from_markup(
                f"[grey50]ET: [/grey50][blue]{elapsed_text}[/blue] [grey50]~ETA: [/grey50][blue]{eta_text}[/blue]")

        # 如果没有预估时间，只显示已用时间
        return Text.from_markup(f"[grey50]ET: [/grey50][blue]{elapsed_text}[/blue]")


# 自定义进度条列
class BracketedBarColumn(BarColumn):
    def render(self, task):
        completed = task.completed
        total = task.total
        width = self.bar_width
        if total is None:
            return Text("[-----Initializing...-----]")

        # 检查任务状态
        is_failed = task.fields.get("failed", False)
        is_done = task.finished

        if total <= 0:
            bar = Text(" " * width, style="bar.back")
        else:
            complete_size = min(int(completed / total * width), width) if total > 0 else 0
            bar = Text()

            # 根据任务状态设置不同的样式
            if is_failed:
                # 失败状态：红色进度条
                bar.append("#" * complete_size, style="red")
                bar.append("." * (width - complete_size), style="dim red")
            elif is_done:
                # 完成状态：全绿色进度条
                bar.append("#" * width, style="green")
            else:
                # 正常状态
                bar.append("#" * complete_size, style="green")
                bar.append("." * (width - complete_size), style="dim")

        # 添加方括号
        result = Text("[")
        result.append(bar)
        result.append("]")

        # 添加状态标志
        if is_failed:
            result.append(" ✗", style="bold red")
        elif is_done:
            result.append(" ✓", style="bold green")

        return result


def create_download_progress():
    return Progress(
        CustomSpinnerColumn(),
        TextColumn("[progress.description]{task.description}", justify="left"),
        "[purple][progress.percentage]{task.percentage:>3.2f}%[/purple]",
        BracketedBarColumn(),
        TransferSpeedColumn(),
        DownloadColumn(),
        CustomTimeColumn(),
        transient=False,
    )


def create_progress():
    return Progress(
        CustomSpinnerColumn(),
        TextColumn("[progress.description]{task.description}", justify="left"),
        TextColumn("({task.completed}/{task.total})"),
        "[purple][progress.percentage]{task.percentage:>3.2f}%[/purple]",
        BracketedBarColumn(),
        TextColumn("[red]Failed: {task.fields[failures]}"),
        CustomTimeColumn(show_remaining=False),
        transient=False,
    )


__all__ = ["create_download_progress"]
