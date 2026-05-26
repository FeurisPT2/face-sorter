import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors

# ArcFace (512-D, L2-normalized): cosine distance = 1 - dot(u, v)
# Same person: often < 0.35–0.42; different people: typically > 0.50
DEFAULT_EPS = 0.40
MIN_EPS = 0.26
MAX_EPS = 0.58
SUSPICIOUS_SIM_FLOOR = 0.52


class FaceClusterer:
    @staticmethod
    def _prepare_embeddings(faces_metadata):
        embeddings = [face["embedding"] for face in faces_metadata]
        X = np.array(embeddings, dtype=np.float64)
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        return X / norms

    @staticmethod
    def _cluster_means(X, labels):
        cluster_means = {}
        for label in set(labels):
            if label == -1:
                continue
            idxs = np.where(labels == label)[0]
            mean_emb = np.mean(X[idxs], axis=0)
            norm = np.linalg.norm(mean_emb)
            if norm > 0:
                mean_emb = mean_emb / norm
            cluster_means[int(label)] = mean_emb
        return cluster_means

    @staticmethod
    def _suspicious_threshold(cluster_sims):
        """Per-cluster adaptive threshold from cohesion of ArcFace embeddings."""
        if len(cluster_sims) == 0:
            return SUSPICIOUS_SIM_FLOOR
        median_sim = float(np.median(cluster_sims))
        return max(SUSPICIOUS_SIM_FLOOR, median_sim - 0.14)

    @staticmethod
    def _fit_dbscan(X, eps, min_samples=2):
        db = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        return db.fit_predict(X)

    @staticmethod
    def _knee_eps_from_kdist(k_distances):
        """Estimate DBSCAN eps near the knee of sorted k-NN distances."""
        sorted_d = np.sort(k_distances)
        n = len(sorted_d)
        if n < 3:
            return float(np.median(sorted_d))

        x = np.linspace(0.0, 1.0, n)
        y = (sorted_d - sorted_d[0]) / (sorted_d[-1] - sorted_d[0] + 1e-9)
        line = x
        dist_to_line = y - line
        knee_idx = int(np.argmax(dist_to_line))
        return float(sorted_d[knee_idx])

    @staticmethod
    def _estimate_eps_candidates(X, min_samples=2):
        """
        Build eps candidates from k-NN distance distribution (data-driven),
        then merge with a coarse grid for ArcFace yearbook photos.
        """
        n = len(X)
        if n < 2:
            return [DEFAULT_EPS]

        k = min(min_samples, n - 1)
        nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine")
        nn.fit(X)
        distances, _ = nn.kneighbors(X)
        k_dists = distances[:, k]

        knee_eps = FaceClusterer._knee_eps_from_kdist(k_dists)
        median_eps = float(np.median(k_dists))
        p45 = float(np.percentile(k_dists, 45))
        p55 = float(np.percentile(k_dists, 55))
        p65 = float(np.percentile(k_dists, 65))

        seeds = [knee_eps, median_eps, p45, p55, p65]
        candidates = set()
        for seed in seeds:
            for mult in (0.88, 0.94, 1.0, 1.06, 1.12):
                candidates.add(round(seed * mult, 3))

        for base in np.linspace(0.30, 0.52, 9):
            candidates.add(round(float(base), 3))

        bounded = sorted({c for c in candidates if MIN_EPS <= c <= MAX_EPS})
        if not bounded:
            bounded = [0.34, 0.38, DEFAULT_EPS, 0.44, 0.48]
        return bounded

    @staticmethod
    def _refine_eps_candidates(best_eps):
        fine = set()
        for delta in (-0.04, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04):
            val = round(best_eps + delta, 3)
            if MIN_EPS <= val <= MAX_EPS:
                fine.add(val)
        return sorted(fine)

    @staticmethod
    def _score_clustering(X, labels, min_samples=2):
        """
        Face Clustering Quality Score v2 for ArcFace embeddings.
        Higher is better. Returns (score, debug_dict).
        """
        n = len(labels)
        if n == 0:
            return -1.0, {}

        noise_count = int(np.sum(labels == -1))
        noise_ratio = noise_count / n

        cluster_means = FaceClusterer._cluster_means(X, labels)
        multi_sizes = []
        cohesion_weighted = 0.0
        clustered_faces = 0
        suspicious_count = 0
        weak_clusters = 0
        total_multi_clusters = 0

        for label, mean_emb in cluster_means.items():
            idxs = np.where(labels == label)[0]
            size = len(idxs)
            if size < min_samples:
                continue

            total_multi_clusters += 1
            multi_sizes.append(size)
            embs = X[idxs]
            sims = embs @ mean_emb
            clustered_faces += size

            cohesion_weighted += float(np.sum(sims))
            susp_th = FaceClusterer._suspicious_threshold(sims)
            suspicious_count += int(np.sum(sims < susp_th))

            if float(np.min(sims)) < 0.50:
                weak_clusters += 1

        if clustered_faces == 0:
            return -1.0, {"noise_ratio": noise_ratio}

        f_coverage = clustered_faces / n
        f_cohesion = cohesion_weighted / clustered_faces
        f_purity = 1.0 - (suspicious_count / clustered_faces)

        # Penalize clusters that likely merged different people (low min similarity)
        f_merge_quality = 1.0 - (weak_clusters / max(total_multi_clusters, 1))

        # Penalize over-fragmentation (too many small multi-face groups)
        expected_max_groups = max(2, n // 3)
        fragment_ratio = min(1.0, total_multi_clusters / expected_max_groups)
        f_fragment = max(0.0, fragment_ratio - 1.0)  # 0 if within budget

        # Allow some singleton/noise faces; penalize only excess noise
        noise_excess = max(0.0, noise_ratio - 0.20) / 0.80

        # Optional silhouette on clustered points (skip for very large sets)
        f_silhouette = 0.0
        valid_labels = labels[labels != -1]
        if 10 < n <= 2500 and len(set(valid_labels)) >= 2 and clustered_faces >= 5:
            try:
                from sklearn.metrics import silhouette_score

                mask = labels != -1
                f_silhouette = max(0.0, silhouette_score(X[mask], labels[mask], metric="cosine"))
            except Exception:
                f_silhouette = 0.0

        base = (
            0.32 * f_coverage
            + 0.28 * f_cohesion
            + 0.22 * f_purity
            + 0.10 * f_merge_quality
            + 0.08 * f_silhouette
        )
        score = base * (1.0 - 0.35 * noise_excess) * (1.0 - 0.20 * f_fragment)

        debug = {
            "coverage": round(f_coverage, 4),
            "cohesion": round(f_cohesion, 4),
            "purity": round(f_purity, 4),
            "merge_quality": round(f_merge_quality, 4),
            "silhouette": round(f_silhouette, 4),
            "noise_ratio": round(noise_ratio, 4),
            "clusters": total_multi_clusters,
            "suspicious": suspicious_count,
            "score": round(score, 4),
        }
        return score, debug

    @staticmethod
    def cluster_faces(faces_metadata, eps=DEFAULT_EPS, min_samples=2, metric="cosine"):
        """
        Clusters faces from L2-normalized ArcFace (512-D) embeddings using DBSCAN
        with cosine distance.
        """
        if not faces_metadata:
            return [], {}

        X = FaceClusterer._prepare_embeddings(faces_metadata)
        labels = FaceClusterer._fit_dbscan(X, eps, min_samples=min_samples)
        cluster_means = FaceClusterer._cluster_means(X, labels)

        clustered_groups = {}
        updated_faces = []
        next_noise_id = 1

        for idx, face in enumerate(faces_metadata):
            label = int(labels[idx])
            face_copy = face.copy()
            face_copy["is_suspicious"] = False
            face_copy["similarity"] = 1.0

            if label != -1 and label in cluster_means:
                emb = X[idx]
                mean_emb = cluster_means[label]
                sim = float(np.dot(emb, mean_emb))
                face_copy["similarity"] = sim

                idxs = np.where(labels == label)[0]
                cluster_sims = X[idxs] @ mean_emb
                if sim < FaceClusterer._suspicious_threshold(cluster_sims):
                    face_copy["is_suspicious"] = True

            if "embedding" in face_copy:
                del face_copy["embedding"]

            if label == -1:
                cluster_id = f"person_unidentified_{next_noise_id}"
                person_name = f"Người chưa biết {next_noise_id}"
                next_noise_id += 1
            else:
                cluster_id = f"person_group_{label}"
                person_name = f"Nhóm người {label + 1}"

            face_copy["cluster_id"] = cluster_id
            face_copy["person_name"] = person_name
            updated_faces.append(face_copy)

            if cluster_id not in clustered_groups:
                clustered_groups[cluster_id] = {
                    "cluster_id": cluster_id,
                    "person_name": person_name,
                    "faces": [],
                }
            clustered_groups[cluster_id]["faces"].append(face_copy)

        sorted_groups = sorted(
            clustered_groups.values(), key=lambda g: len(g["faces"]), reverse=True
        )
        sorted_groups_dict = {g["cluster_id"]: g for g in sorted_groups}
        return updated_faces, sorted_groups_dict

    @staticmethod
    def auto_tune_epsilon(faces_metadata, min_samples=2, verbose=True, eps_offset=0.0):
        """
        Two-stage search for optimal DBSCAN eps:
        1) Data-driven candidates from k-NN distance knee + percentiles
        2) Fine grid around the best coarse eps

        Returns:
            float: optimal epsilon
        """
        if not faces_metadata or len(faces_metadata) < 2:
            return DEFAULT_EPS

        X = FaceClusterer._prepare_embeddings(faces_metadata)
        coarse_candidates = FaceClusterer._estimate_eps_candidates(X, min_samples=min_samples)

        best_eps = DEFAULT_EPS
        best_score = -1.0
        best_debug = {}

        for eps in coarse_candidates:
            labels = FaceClusterer._fit_dbscan(X, eps, min_samples=min_samples)
            score, debug = FaceClusterer._score_clustering(X, labels, min_samples=min_samples)
            if verbose:
                print(
                    f"[Auto-Tune:coarse] eps={eps:.3f} score={score:.4f} "
                    f"coverage={debug.get('coverage')} purity={debug.get('purity')} "
                    f"noise={debug.get('noise_ratio')} clusters={debug.get('clusters')}"
                )
            if score > best_score:
                best_score = score
                best_eps = eps
                best_debug = debug

        for eps in FaceClusterer._refine_eps_candidates(best_eps):
            if eps in coarse_candidates:
                continue
            labels = FaceClusterer._fit_dbscan(X, eps, min_samples=min_samples)
            score, debug = FaceClusterer._score_clustering(X, labels, min_samples=min_samples)
            if verbose:
                print(f"[Auto-Tune:fine] eps={eps:.3f} score={score:.4f}")
            if score > best_score:
                best_score = score
                best_eps = eps
                best_debug = debug

        if eps_offset:
            best_eps = float(np.clip(best_eps + eps_offset, MIN_EPS, MAX_EPS))
        if verbose:
            print(
                f"[Auto-Tune] Done. eps={best_eps:.3f} score={best_score:.4f} "
                f"offset={eps_offset:.3f} details={best_debug}"
            )
        return float(best_eps)
