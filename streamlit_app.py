# ENSURE-6G • TMS Rail Demo  ▸  v5 — modularized

from ensure6g.sidebar import init_session_state, render_sidebar
from ensure6g.simulation import auto_advance, compute_frame, prepare_route
from ensure6g.theme import apply_theme, setup_page
from ensure6g.views import render_header_and_timeline, render_tabs


def main():
    setup_page()
    apply_theme()

    init_session_state()
    controls = render_sidebar()

    secs, route_df, seg_labels = prepare_route(controls["sim_minutes"])
    auto_advance(controls["play_rate"], secs)
    frame = compute_frame(route_df, seg_labels, secs, controls)

    render_header_and_timeline(frame, secs, route_df)
    render_tabs(frame, route_df, secs)


if __name__ == "__main__":
    main()
