from __future__ import annotations

from .analytics import AnalyticsStore, CATEGORIES, DEFAULT_DATABASE_PATH


def main() -> None:
    store = AnalyticsStore(DEFAULT_DATABASE_PATH)
    metrics = store.metrics()
    overall = metrics["overall"]

    print("Anonymous CTA analytics")
    print(
        f"overall  result_view={overall['result_view']} "
        f"cta_click={overall['cta_click']} ctr={overall['ctr_percent']:.2f}%"
    )
    for category in CATEGORIES:
        values = metrics["categories"][category]
        print(
            f"{category:<14} result_view={values['result_view']} "
            f"cta_click={values['cta_click']} ctr={values['ctr_percent']:.2f}%"
        )


if __name__ == "__main__":
    main()
