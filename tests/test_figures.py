from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
from dataexcept import DataLoadingError, FileWriteError

from pt_wage_gap.figures import plot_conditional_residuals, plot_gap_history


@pytest.mark.parametrize(
    ("plot", "csv"),
    [
        (plot_gap_history, "year,wage_shortfall_pct,productivity_shortfall_pct\n2024,1,2\n"),
        (plot_conditional_residuals, "year,multiplicative_residual_pct\n2024,3\n"),
    ],
)
def test_figures_classify_load_and_save_failures(
    tmp_path: Path, plot: Callable[[Path, Path], None], csv: str
) -> None:
    source = tmp_path / "input.csv"
    output = tmp_path / "figure.png"

    with pytest.raises(DataLoadingError) as missing:
        plot(source, output)
    assert missing.value.source == str(source)
    assert isinstance(missing.value.original, FileNotFoundError)
    assert missing.value.__cause__ is missing.value.original

    source.write_text(csv, encoding="utf-8")
    plot(source, output)
    assert output.is_file()

    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    output = blocker / "figure.png"
    with pytest.raises(FileWriteError) as blocked:
        plot(source, output)
    assert blocked.value.path == str(output)
    assert isinstance(blocked.value.original, OSError)
    assert blocked.value.__cause__ is blocked.value.original
    assert not plt.get_fignums()


def test_empty_figure_csv_is_a_loading_error(tmp_path: Path) -> None:
    source = tmp_path / "empty.csv"
    source.touch()

    with pytest.raises(DataLoadingError) as caught:
        plot_gap_history(source, tmp_path / "figure.png")
    assert caught.value.source == str(source)
    assert caught.value.__cause__ is caught.value.original
