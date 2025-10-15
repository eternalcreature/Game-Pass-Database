from utils.igdb_retriever import get_IGDB_data
from utils.igdb_parser import IGDBParser
import json


def update_igdb(pid, id, main_version=True):
    igdb_data, _ = get_IGDB_data(id)
    processed = IGDBParser(igdb_data).to_dict()
    with open(f"mnt/xbox/gp_new/{pid}.json", "r", encoding="utf8") as f:
        all_data = json.load(f)
    if main_version:
        all_data["igdb_meta"]["main"] = processed
        all_data["basic_info"]["base_id"] = id
    else:
        all_data["igdb_meta"]["specific"] = processed
        all_data["basic_info"]["specific_id"] = id
    with open(f"mnt/xbox/gp_new/{pid}.json", "w", encoding="utf8") as f:
        json.dump(all_data, f, indent=2)
