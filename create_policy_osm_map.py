#!/usr/bin/env python3
"""Draw modified policy links on an OpenStreetMap basemap."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import contextily as cx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely.geometry import LineString


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DEFAULT_POLICY_ZIP = PROJECT_DIR / "run-459-files.zip"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "outputs"

CATEGORY_LINKS = {
    "Carola Bridge restricted": {
        "4214231",
        "901959078",
    },
    "Alternative bridges modified": {
        "-264360396#1",
        "-264360404",
        "-504890257",
        "1031454500",
        "12497357",
        "505502627#0",
    },
    "New bike-only connectivity": {
        "5b392c03-f62d-48ad-bb53-dfe310f1ba1c",
        "5c67424c-adc0-439e-92d9-ba6f7471d080",
        "859a1330-0bed-45b2-ad70-7c8638a455b7",
        "9305fbe8-9543-4eae-91a1-f5e29a998590",
        "a677d4d0-3316-466b-b307-690a5740d877",
        "ccf512b2-7eca-406d-b4cf-4b5f2ac8293b",
        "d4de14b2-f040-4589-a0a1-a7170d60bad7",
        "d5c6ef5d-151d-46ca-8106-085fea5b857a",
    },
    "Feeder/corridor modified": {
        "-1329159900",
        "-294983108",
        "-369971087",
        "-99478092",
        "1036528789",
        "1108789888",
        "138307399",
        "150611226",
        "213544718",
        "233822748#1",
        "237502199",
        "24209438",
        "25702467#0",
        "379745367",
        "415552984",
        "4214230",
        "439458122",
        "443697736",
        "4539657",
        "504885692",
        "657862430",
        "867018480",
    },
}

LINK_TO_CATEGORY = {
    link_id: category
    for category, link_ids in CATEGORY_LINKS.items()
    for link_id in link_ids
}

STYLE = {
    "Carola Bridge restricted": {
        "color": "#d7191c",
        "linewidth": 5.8,
        "linestyle": "-",
        "zorder": 8,
    },
    "Alternative bridges modified": {
        "color": "#174a8b",
        "linewidth": 5.0,
        "linestyle": "-",
        "zorder": 7,
    },
    "New bike-only connectivity": {
        "color": "#5ca319",
        "linewidth": 4.2,
        "linestyle": (0, (4, 2)),
        "zorder": 9,
    },
    "Feeder/corridor modified": {
        "color": "#f28e1c",
        "linewidth": 3.6,
        "linestyle": "-",
        "zorder": 6,
    },
}

LABEL_RULES = {
    "Albert Bridge": {
        "match": lambda row: "Albert" in row.get("name", ""),
        "offset": (-230, 10),
    },
    "Augustus Bridge": {
        "match": lambda row: "Augustus" in row.get("name", ""),
        "offset": (145, 235),
    },
    "Carola Bridge": {
        "match": lambda row: row["category"] == "Carola Bridge restricted",
        "offset": (155, -55),
    },
    "Carolaplatz": {
        "match": lambda row: "Carolaplatz" in row.get("name", ""),
        "offset": (170, -85),
    },
    "Sachsenplatz": {
        "match": lambda row: "Sachsenplatz" in row.get("name", ""),
        "offset": (80, -70),
    },
    "Neustadter Markt": {
        "match": lambda row: "Neust" in row.get("name", ""),
        "offset": (-240, 15),
    },
    "Glacisstrasse": {
        "match": lambda row: "Glacis" in row.get("name", ""),
        "offset": (80, 165),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-zip", type=Path, default=DEFAULT_POLICY_ZIP)
    parser.add_argument("--policy-json", default="HA1_Policy_20260525.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dpi", type=int, default=350)
    return parser.parse_args()


def first_zip_member(archive: zipfile.ZipFile, suffix: str) -> str:
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if not matches:
        raise FileNotFoundError(f"No zip member ending with {suffix}")
    return matches[0]


def iter_operations(operations: list[dict]):
    for operation in operations:
        yield operation
        payload = operation.get("payload") or {}
        for nested in payload.get("modifications") or []:
            yield nested


def load_policy_links(policy_zip: Path, policy_json: str) -> tuple[dict[str, dict], set[str]]:
    with zipfile.ZipFile(policy_zip) as archive:
        operations = json.loads(archive.read(policy_json).decode("utf-8"))

    links: dict[str, dict] = {}
    deleted_link_ids: set[str] = set()
    for operation in iter_operations(operations):
        payload = operation.get("payload") or {}
        properties = payload.get("properties") or {}
        link_id = payload.get("id") or properties.get("id")
        if not link_id:
            continue

        if operation.get("type") == "DeleteLink":
            deleted_link_ids.add(link_id)
            continue

        if operation.get("type") not in {"AddLink", "UpdateLink"}:
            continue

        links[link_id] = {
            "link_id": link_id,
            "category": LINK_TO_CATEGORY.get(link_id, "Other modified link"),
            "name": properties.get("name", ""),
            "length_m": properties.get("length", ""),
            "freespeed_m_s": properties.get("freespeed", ""),
            "capacity": properties.get("capacity", ""),
            "lanes": properties.get("lanes", ""),
            "modes": properties.get("modes", ""),
            "from_id_policy": properties.get("fromId", ""),
            "to_id_policy": properties.get("toId", ""),
        }

    return links, deleted_link_ids


def extract_network_geometries(
    policy_zip: Path, link_info: dict[str, dict], deleted_link_ids: set[str]
) -> gpd.GeoDataFrame:
    target_ids = set(link_info) - deleted_link_ids

    with zipfile.ZipFile(policy_zip) as archive:
        network_member = first_zip_member(archive, "output_network.xml.gz")
        with gzip.open(archive.open(network_member), "rb") as handle:
            nodes: dict[str, tuple[float, float]] = {}
            links: dict[str, dict] = {}
            in_nodes = False
            in_links = False

            for event, elem in ET.iterparse(handle, events=("start", "end")):
                if event == "start" and elem.tag == "nodes":
                    in_nodes = True
                elif event == "end" and elem.tag == "nodes":
                    in_nodes = False
                    elem.clear()
                elif event == "start" and elem.tag == "links":
                    in_links = True
                elif event == "end" and elem.tag == "links":
                    break
                elif event == "end" and in_nodes and elem.tag == "node":
                    nodes[elem.attrib["id"]] = (
                        float(elem.attrib["x"]),
                        float(elem.attrib["y"]),
                    )
                    elem.clear()
                elif event == "end" and in_links and elem.tag == "link":
                    link_id = elem.attrib.get("id")
                    if link_id in target_ids:
                        links[link_id] = dict(elem.attrib)
                    elem.clear()

    rows = []
    for link_id, network_link in links.items():
        from_id = network_link["from"]
        to_id = network_link["to"]
        if from_id not in nodes or to_id not in nodes:
            continue

        row = {
            **link_info[link_id],
            "from_id": from_id,
            "to_id": to_id,
            "network_length_m": network_link.get("length", ""),
            "network_freespeed_m_s": network_link.get("freespeed", ""),
            "network_capacity": network_link.get("capacity", ""),
            "geometry": LineString([nodes[from_id], nodes[to_id]]),
        }
        rows.append(row)

    missing = sorted(target_ids - set(links))
    if missing:
        print("Warning: missing link geometries:", ", ".join(missing))
    if deleted_link_ids:
        print("Deleted policy links excluded:", ", ".join(sorted(deleted_link_ids)))

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:25832")
    gdf.attrs["missing_link_geometries"] = missing
    gdf.attrs["deleted_policy_links"] = sorted(deleted_link_ids)
    return gdf


def save_link_tables(gdf: gpd.GeoDataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = output_dir / "policy_links_from_network.geojson"
    try:
        if geojson_path.exists():
            geojson_path.unlink()
        gdf.to_file(geojson_path, driver="GeoJSON")
    except Exception as exc:
        print(f"Warning: could not write {geojson_path}: {exc}")

    missing_path = output_dir / "excluded_or_missing_policy_link_geometries.txt"
    missing = gdf.attrs.get("missing_link_geometries", [])
    deleted = gdf.attrs.get("deleted_policy_links", [])
    lines = []
    if deleted:
        lines.append(
            "These policy link IDs were present in HA1_Policy_20260525.json "
            "but were later removed by DeleteLink operations, so they are not "
            "present in the final policy output_network.xml.gz:"
        )
        lines.extend(deleted)
        lines.append("")

    if missing:
        lines.append(
            "These policy link IDs were expected in the final network but were "
            "not found in output_network.xml.gz:"
        )
        lines.extend(missing)
    elif not deleted:
        lines.append("All expected policy link IDs were found in output_network.xml.gz.")

    try:
        missing_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"Warning: could not write {missing_path}: {exc}")

    csv_path = output_dir / "policy_links_from_network.csv"
    columns = [
        "link_id",
        "category",
        "name",
        "from_id",
        "to_id",
        "length_m",
        "freespeed_m_s",
        "capacity",
        "lanes",
        "modes",
    ]
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for _, row in gdf.iterrows():
                writer.writerow({column: row.get(column, "") for column in columns})
    except Exception as exc:
        print(f"Warning: could not write {csv_path}: {exc}")


def plot_category(ax, gdf: gpd.GeoDataFrame, category: str) -> None:
    subset = gdf[gdf["category"] == category]
    if subset.empty:
        return

    style = STYLE[category]
    if category != "New bike-only connectivity":
        subset.plot(
            ax=ax,
            color="white",
            linewidth=style["linewidth"] + 3.0,
            alpha=0.92,
            zorder=style["zorder"] - 1,
        )
    subset.plot(
        ax=ax,
        color=style["color"],
        linewidth=style["linewidth"],
        linestyle=style["linestyle"],
        zorder=style["zorder"],
    )


def add_labels(ax, gdf_3857: gpd.GeoDataFrame) -> None:
    for label, rule in LABEL_RULES.items():
        matches = gdf_3857[gdf_3857.apply(rule["match"], axis=1)]
        if matches.empty:
            continue

        point = matches.unary_union.centroid
        dx, dy = rule["offset"]
        ax.annotate(
            label,
            xy=(point.x, point.y),
            xytext=(point.x + dx, point.y + dy),
            textcoords="data",
            fontsize=10,
            fontweight="bold",
            color="#18202a",
            ha="center",
            va="center",
            arrowprops={
                "arrowstyle": "-",
                "color": "#59636f",
                "lw": 0.8,
                "alpha": 0.8,
            },
            bbox={
                "boxstyle": "round,pad=0.22",
                "facecolor": "white",
                "edgecolor": "#cfd6dd",
                "alpha": 0.88,
            },
            zorder=20,
        )


def add_legend(ax) -> None:
    handles = [
        Line2D(
            [0],
            [0],
            color=STYLE["Carola Bridge restricted"]["color"],
            lw=5,
            label="Carola Bridge restricted",
        ),
        Line2D(
            [0],
            [0],
            color=STYLE["Alternative bridges modified"]["color"],
            lw=5,
            label="Alternative bridges modified",
        ),
        Line2D(
            [0],
            [0],
            color=STYLE["New bike-only connectivity"]["color"],
            lw=4,
            linestyle=(0, (4, 2)),
            label="New bike-only connectivity",
        ),
        Line2D(
            [0],
            [0],
            color=STYLE["Feeder/corridor modified"]["color"],
            lw=4,
            label="Feeder/corridor modified",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="lower left",
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#c8cfd6",
        fontsize=10,
        title="Policy road segments",
        title_fontsize=10,
    )


def add_north_arrow(ax) -> None:
    ax.annotate(
        "",
        xy=(0.945, 0.905),
        xytext=(0.945, 0.795),
        xycoords="axes fraction",
        arrowprops={
            "arrowstyle": "-|>",
            "lw": 2.2,
            "color": "#111111",
            "mutation_scale": 22,
        },
        zorder=60,
    )
    ax.text(
        0.945,
        0.925,
        "N",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color="#111111",
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": "white",
            "edgecolor": "#c8cfd6",
            "alpha": 0.88,
        },
        zorder=61,
    )


def add_scale_bar(ax, gdf_3857: gpd.GeoDataFrame, length_m: int = 250) -> None:
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    width = x_max - x_min
    height = y_max - y_min

    lat = gdf_3857.to_crs(epsg=4326).unary_union.centroid.y
    projected_length = length_m / math.cos(math.radians(lat))

    x0 = x_max - projected_length - width * 0.055
    y0 = y_min + height * 0.070
    tick = height * 0.015

    ax.add_patch(
        Rectangle(
            (x0 - width * 0.020, y0 - height * 0.040),
            projected_length + width * 0.040,
            height * 0.110,
            facecolor="white",
            edgecolor="#c8cfd6",
            linewidth=0.9,
            alpha=0.88,
            zorder=55,
        )
    )
    ax.plot([x0, x0 + projected_length], [y0, y0], color="#111111", linewidth=3.0, zorder=56)
    ax.plot([x0, x0], [y0 - tick, y0 + tick], color="#111111", linewidth=2.0, zorder=56)
    ax.plot(
        [x0 + projected_length, x0 + projected_length],
        [y0 - tick, y0 + tick],
        color="#111111",
        linewidth=2.0,
        zorder=56,
    )
    ax.text(
        x0 + projected_length / 2,
        y0 + height * 0.033,
        f"{length_m} m",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color="#111111",
        zorder=57,
    )


def draw_map(gdf: gpd.GeoDataFrame, output_dir: Path, dpi: int) -> None:
    gdf_3857 = gdf.to_crs(epsg=3857)
    minx, miny, maxx, maxy = gdf_3857.total_bounds
    pad_x = max((maxx - minx) * 0.05, 140)
    pad_y = max((maxy - miny) * 0.11, 150)

    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)

    cx.add_basemap(
        ax,
        source=cx.providers.OpenStreetMap.Mapnik,
        crs=gdf_3857.crs,
        zoom=15,
        attribution_size=7,
        alpha=0.38,
    )

    for category in [
        "Feeder/corridor modified",
        "Alternative bridges modified",
        "Carola Bridge restricted",
        "New bike-only connectivity",
    ]:
        plot_category(ax, gdf_3857, category)

    add_labels(ax, gdf_3857)
    add_legend(ax)
    add_north_arrow(ax)
    add_scale_bar(ax, gdf_3857)

    ax.set_title(
        "Carola Bridge Policy: Modified Road Segments",
        fontsize=16,
        fontweight="bold",
        pad=12,
    )
    ax.set_axis_off()

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "carola_policy_osm_map.png"
    pdf_path = output_dir / "carola_policy_osm_map.pdf"
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    link_info, deleted_link_ids = load_policy_links(args.policy_zip, args.policy_json)
    gdf = extract_network_geometries(args.policy_zip, link_info, deleted_link_ids)
    if gdf.empty:
        raise RuntimeError("No policy link geometries were extracted from the network.")

    save_link_tables(gdf, args.output_dir)
    draw_map(gdf, args.output_dir, args.dpi)

    print(f"Extracted policy links: {len(gdf)}")
    print("Category counts:")
    for category, count in gdf["category"].value_counts().items():
        print(f"  {category}: {count}")
    print(f"Outputs written to: {args.output_dir}")


if __name__ == "__main__":
    main()
