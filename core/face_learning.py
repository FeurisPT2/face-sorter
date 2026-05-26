import json
import time
from pathlib import Path
from typing import Optional

import numpy as np

# Gray zone for ArcFace centroid similarity — likely split of same person
SUGGEST_SIM_MIN = 0.46
SUGGEST_SIM_MAX = 0.72
EPS_OFFSET_MIN = -0.08
EPS_OFFSET_MAX = 0.08


class FaceLearningStore:
  """Persistent pairwise feedback (must-link / cannot-link) for clustering."""

  def __init__(self, data_path: Path):
    self.data_path = Path(data_path)
    self.data_path.parent.mkdir(parents=True, exist_ok=True)
    self._data = self._load()

  def _load(self):
    if self.data_path.exists():
      try:
        with open(self.data_path, "r", encoding="utf-8") as f:
          return json.load(f)
      except (json.JSONDecodeError, OSError):
        pass
    return {
      "must_link": [],
      "cannot_link": [],
      "dismissed": [],
      "feedback": [],
      "eps_offset": 0.0,
      "person_prototypes": [],
    }

  def save(self):
    with open(self.data_path, "w", encoding="utf-8") as f:
      json.dump(self._data, f, ensure_ascii=False, indent=2)

  @staticmethod
  def pair_key(cluster_a: str, cluster_b: str) -> str:
    a, b = sorted([cluster_a, cluster_b])
    return f"{a}::{b}"

  def _pair_list(self, field: str) -> set:
    return set(self._data.get(field, []))

  def is_cannot_link(self, cluster_a: str, cluster_b: str) -> bool:
    return self.pair_key(cluster_a, cluster_b) in self._pair_list("cannot_link")

  def is_dismissed(self, cluster_a: str, cluster_b: str) -> bool:
    return self.pair_key(cluster_a, cluster_b) in self._pair_list("dismissed")

  def is_must_link(self, cluster_a: str, cluster_b: str) -> bool:
    return self.pair_key(cluster_a, cluster_b) in self._pair_list("must_link")

  def get_eps_offset(self) -> float:
    return float(self._data.get("eps_offset", 0.0))

  def get_stats(self):
    return {
      "must_link_count": len(self._data.get("must_link", [])),
      "cannot_link_count": len(self._data.get("cannot_link", [])),
      "feedback_count": len(self._data.get("feedback", [])),
      "eps_offset": round(self.get_eps_offset(), 4),
      "prototype_count": len(self._data.get("person_prototypes", [])),
    }

  def clear_all(self):
    """Xóa toàn bộ dữ liệu học (must/cannot link, feedback, prototypes, eps offset)."""
    self._data = {
      "must_link": [],
      "cannot_link": [],
      "dismissed": [],
      "feedback": [],
      "eps_offset": 0.0,
      "person_prototypes": [],
    }
    self.save()

  def record_feedback(
    self,
    cluster_a: str,
    cluster_b: str,
    *,
    same: Optional[bool],
    similarity: float,
    skipped: bool = False,
  ):
    key = self.pair_key(cluster_a, cluster_b)
    entry = {
      "pair": key,
      "cluster_a": cluster_a,
      "cluster_b": cluster_b,
      "same": same,
      "similarity": round(float(similarity), 4),
      "skipped": skipped,
      "ts": int(time.time()),
    }
    self._data.setdefault("feedback", []).append(entry)
    # Keep last 500 feedback entries
    if len(self._data["feedback"]) > 500:
      self._data["feedback"] = self._data["feedback"][-500:]

    dismissed = self._pair_list("dismissed")
    must = self._pair_list("must_link")
    cannot = self._pair_list("cannot_link")

    if skipped:
      dismissed.add(key)
      self._data["dismissed"] = sorted(dismissed)
    elif same is True:
      must.add(key)
      cannot.discard(key)
      dismissed.discard(key)
      self._data["must_link"] = sorted(must)
      self._data["cannot_link"] = sorted(cannot)
    elif same is False:
      cannot.add(key)
      must.discard(key)
      dismissed.discard(key)
      self._data["cannot_link"] = sorted(cannot)
      self._data["must_link"] = sorted(must)

    self._recompute_eps_offset()
    self.save()
    return entry

  def _recompute_eps_offset(self):
    """Derive DBSCAN eps nudge from confirmed same/different answers."""
    feedback = [
      f
      for f in self._data.get("feedback", [])
      if not f.get("skipped") and f.get("same") is not None
    ]
    if not feedback:
      self._data["eps_offset"] = 0.0
      return

    offset = 0.0
    recent = feedback[-80:]
    for item in recent:
      sim = float(item.get("similarity", 0.5))
      if item["same"]:
        # Split clusters but user says same → loosen clustering
        if sim >= 0.48:
          offset += 0.008 + max(0.0, 0.58 - sim) * 0.04
      else:
        # Merged visually similar but user says different → tighten
        if sim >= 0.44:
          offset -= 0.010 + max(0.0, sim - 0.50) * 0.05

    offset = float(np.clip(offset, EPS_OFFSET_MIN, EPS_OFFSET_MAX))
    self._data["eps_offset"] = round(offset, 4)

  def add_person_prototype(self, person_name: str, embedding: list):
    """Remember named person embedding for future scans (lightweight memory)."""
    if not person_name or not embedding:
      return
    vec = np.array(embedding, dtype=np.float64)
    norm = np.linalg.norm(vec)
    if norm <= 0:
      return
    vec = (vec / norm).tolist()

    prototypes = self._data.setdefault("person_prototypes", [])
    for proto in prototypes:
      if proto.get("name") == person_name:
        old = np.array(proto["embedding"], dtype=np.float64)
        merged = old + np.array(vec)
        merged = merged / (np.linalg.norm(merged) + 1e-9)
        proto["embedding"] = merged.tolist()
        proto["updated_at"] = int(time.time())
        self.save()
        return

    prototypes.append(
      {
        "name": person_name,
        "embedding": vec,
        "updated_at": int(time.time()),
      }
    )
    if len(prototypes) > 200:
      self._data["person_prototypes"] = prototypes[-200:]
    self.save()

  def get_must_link_components(self) -> dict:
    """Union-find: cluster_id -> representative cluster_id."""
    parent = {}

    def find(x):
      parent.setdefault(x, x)
      if parent[x] != x:
        parent[x] = find(parent[x])
      return parent[x]

    def union(a, b):
      ra, rb = find(a), find(b)
      if ra != rb:
        parent[rb] = ra

    for key in self._data.get("must_link", []):
      parts = key.split("::", 1)
      if len(parts) == 2:
        union(parts[0], parts[1])

    return {cid: find(cid) for cid in parent}

  @staticmethod
  def build_cluster_centroids(scan_results, clustered_groups):
    face_by_id = {f["id"]: f for f in scan_results}
    centroids = {}
    meta = {}

    groups = (
      clustered_groups.values()
      if isinstance(clustered_groups, dict)
      else clustered_groups
    )
    for group in groups:
      cid = group["cluster_id"]
      embs = []
      for face in group.get("faces", []):
        raw = face_by_id.get(face["id"])
        if raw and "embedding" in raw:
          embs.append(raw["embedding"])
      if not embs:
        continue
      X = np.array(embs, dtype=np.float64)
      norms = np.linalg.norm(X, axis=1, keepdims=True)
      norms = np.where(norms > 0, norms, 1.0)
      X = X / norms
      mean = np.mean(X, axis=0)
      norm = np.linalg.norm(mean)
      if norm > 0:
        mean = mean / norm
      centroids[cid] = mean
      meta[cid] = {
        "person_name": group.get("person_name", cid),
        "face_count": len(group.get("faces", [])),
        "sample_crop": group["faces"][0].get("crop_image") if group.get("faces") else None,
      }
    return centroids, meta

  def suggest_pairs(self, scan_results, clustered_groups, limit=8):
    centroids, meta = self.build_cluster_centroids(scan_results, clustered_groups)
    cluster_ids = list(centroids.keys())
    if len(cluster_ids) < 2:
      return []

    suggestions = []
    for i in range(len(cluster_ids)):
      for j in range(i + 1, len(cluster_ids)):
        ca, cb = cluster_ids[i], cluster_ids[j]
        if self.is_cannot_link(ca, cb) or self.is_must_link(ca, cb):
          continue
        if self.is_dismissed(ca, cb):
          continue

        sim = float(np.dot(centroids[ca], centroids[cb]))
        if sim < SUGGEST_SIM_MIN or sim > SUGGEST_SIM_MAX:
          continue

        # Priority: borderline similarity + smaller groups (likely duplicate splits)
        size_a = meta[ca]["face_count"]
        size_b = meta[cb]["face_count"]
        borderline = 1.0 - abs(sim - 0.56) / 0.20
        priority = borderline * (1.0 + 2.0 / (size_a + size_b))

        suggestions.append(
          {
            "cluster_a": ca,
            "cluster_b": cb,
            "similarity": round(sim, 4),
            "cosine_distance": round(1.0 - sim, 4),
            "priority": round(priority, 4),
            "person_a": meta[ca]["person_name"],
            "person_b": meta[cb]["person_name"],
            "face_count_a": size_a,
            "face_count_b": size_b,
            "sample_crop_a": meta[ca]["sample_crop"],
            "sample_crop_b": meta[cb]["sample_crop"],
          }
        )

    suggestions.sort(key=lambda x: x["priority"], reverse=True)
    return suggestions[:limit]

  def prototype_hints_for_clusters(self, scan_results, clustered_groups):
    """Match unnamed/small clusters to learned named prototypes."""
    centroids, meta = self.build_cluster_centroids(scan_results, clustered_groups)
    prototypes = self._data.get("person_prototypes", [])
    if not prototypes or not centroids:
      return []

    hints = []
    for cid, centroid in centroids.items():
      name = meta[cid]["person_name"]
      if name and not name.startswith("Nhóm người") and not name.startswith("Người chưa"):
        continue
      best_name = None
      best_sim = 0.0
      for proto in prototypes:
        pvec = np.array(proto["embedding"], dtype=np.float64)
        sim = float(np.dot(centroid, pvec))
        if sim > best_sim:
          best_sim = sim
          best_name = proto["name"]
      if best_name and best_sim >= 0.55:
        hints.append(
          {
            "cluster_id": cid,
            "suggested_name": best_name,
            "similarity": round(best_sim, 4),
          }
        )
    return hints
