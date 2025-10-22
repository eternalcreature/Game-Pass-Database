import glob
import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd


# --- Path configuration ---
INPUT_DIR: str = "mnt/xbox/gp_new/"
json_files: List[str] = glob.glob(os.path.join(INPUT_DIR, "*.json"))


def get_df(
    tier_name: str,
    platform: Optional[str] = None,
    additional_fields: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Load and flatten JSON game data into a pandas DataFrame.

    Each JSON file in `INPUT_DIR` represents a game entry. This function
    extracts data from the specified subscription `tier_name` (e.g., "gamepass")
    and optionally filters by `platform` (e.g., "Xbox", "PC"). Additional nested
    fields can be extracted via `additional_fields`.

    Parameters
    ----------
    tier_name : str
        The subscription tier to extract data from (e.g., "gamepass", "ea_play").
    platform : str, optional
        Optional platform filter. Only include games available on this platform.
    additional_fields : dict[str, list[str] | str], optional
        Mapping of output column names to JSON paths.
        Example:
        >>> {"f2p": ["flags", "f2p"], "genre": ["basic_info", "genre"]}

    Returns
    -------
    pd.DataFrame
        DataFrame with the following columns:
        - `base_id` : str
        - `title` : str
        - `pid` : str
        - `added` : datetime64
        - `removed` : datetime64
        Plus any additional fields specified in `additional_fields`.

    Notes
    -----
    - Non-parseable or missing date values are coerced to NaT.
    - Files that fail to load or parse are skipped with a warning.
    """
    if additional_fields is None:
        additional_fields = {}

    records: List[Dict[str, Any]] = []

    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            basic_info = data.get("basic_info", {})
            base_id = basic_info.get("base_id")
            title = basic_info.get("title")
            pid = basic_info.get("pid")

            # Platform filter (if provided)
            if platform:
                platforms = basic_info.get("platforms", [])
                if not isinstance(platforms, list) or platform not in platforms:
                    continue

            for availability in data.get("availabilities", []):
                tier_data = availability.get(tier_name, {})
                added = tier_data.get("added")
                removed = tier_data.get("removed")

                if not added:
                    continue

                record: Dict[str, Any] = {
                    "base_id": base_id,
                    "title": title,
                    "pid": pid,
                    "added": added,
                    "removed": removed,
                }

                # Extract additional JSON fields
                for col_name, json_path in additional_fields.items():
                    value = data
                    if isinstance(json_path, list):
                        for key in json_path:
                            if isinstance(value, dict):
                                value = value.get(key, {})
                            else:
                                value = None
                                break
                    else:
                        value = data.get(json_path)

                    record[col_name] = value

                records.append(record)

        except Exception as e:
            print(f"⚠️ Failed to process {path}: {e}")

    df = pd.DataFrame(records)
    df["added"] = pd.to_datetime(df["added"], format="%Y-%m-%d", errors="coerce")
    df["removed"] = pd.to_datetime(df["removed"], format="%Y-%m-%d", errors="coerce")
    return df


def collapse_df(df: pd.DataFrame, report: bool = False) -> pd.DataFrame:
    """
    Collapse duplicate game entries based on (base_id, title, removed).

    Within each (base_id, title) group, games are further divided into
    subgroups that share the same `removed` value. For each subgroup,
    the row with the earliest `added` date is selected.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with at least the columns:
        ['base_id', 'title', 'added', 'removed'].
    report : bool, optional
        If True, prints a short summary of the collapsing process.

    Returns
    -------
    pd.DataFrame
        A DataFrame with one row per unique (base_id, title, removed)
        combination, containing the earliest-added row from each subgroup.
    """

    def pick_earliest_added(group: pd.DataFrame) -> pd.DataFrame:
        """Return one row per distinct 'removed' value, choosing earliest 'added'."""
        # Treat NaT in 'removed' as a valid subgroup key
        group = group.copy()
        group["removed_key"] = group["removed"].astype(str)

        # For each removed value, find the row with the earliest added date
        idx = (
            group.groupby("removed_key", dropna=False)["added"]
            .idxmin()
            .dropna()
            .astype(int)
        )
        return group.loc[idx].drop(columns=["removed_key"])

    collapsed = (
        df.groupby(["base_id", "title"], group_keys=False)
        .apply(pick_earliest_added)
        .reset_index(drop=True)
    )

    if report:
        before, after = len(df), len(collapsed)
        print(
            f"Collapsed {before:,} → {after:,} rows "
            f"({before - after:,} merged duplicates)"
        )
        print("\nSample of collapsed entries:")
        print(collapsed.head(10))

    return collapsed


def get_collapsed_df(
    tier_name: str,
    platform: Optional[str] = None,
    additional_fields: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Convenience wrapper combining `get_df()` and `collapse_df()`.

    Parameters
    ----------
    tier_name : str
        The subscription tier name to extract.
    platform : str, optional
        Optional platform filter.
    additional_fields : dict[str, list[str] | str], optional
        Additional fields to extract from JSON data.

    Returns
    -------
    pd.DataFrame
        Collapsed and cleaned DataFrame of games for the given tier.
    """
    df = get_df(tier_name, platform=platform, additional_fields=additional_fields)
    return collapse_df(df)
