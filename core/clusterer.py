import numpy as np
from sklearn.cluster import DBSCAN

class FaceClusterer:
    @staticmethod
    def cluster_faces(faces_metadata, eps=0.42, min_samples=2, metric="cosine"):
        """
        Clusters faces based on their 128-d L2-normalized embeddings using DBSCAN
        with cosine distance metric.
        
        Args:
            faces_metadata (list): List of dictionaries containing face metadata and "embedding".
            eps (float): Maximum cosine distance between two samples (threshold).
                         For L2-normalized SFace embeddings:
                         - cosine_distance = 1 - cosine_similarity
                         - Same person: typically < 0.3
                         - Different person: typically > 0.5
                         - Default 0.42 provides good balance for yearbook photos.
            min_samples (int): The number of samples in a neighborhood for a point to be 
                               considered a core point. Set to 2 so single isolated faces
                               become noise (unidentified) rather than forming their own cluster.
            metric (str): Distance metric to use ('cosine' recommended for normalized embeddings).
            
        Returns:
            list: The updated faces_metadata with a "cluster_id" (str) and "person_name" (str) added.
            dict: A dictionary mapping cluster_id to list of face metadata dicts.
        """
        if not faces_metadata:
            return [], {}
            
        # Extract embeddings
        embeddings = [face["embedding"] for face in faces_metadata]
        X = np.array(embeddings, dtype=np.float64)
        
        # Safety check: ensure embeddings are L2-normalized for cosine metric
        # This handles any edge cases where old non-normalized embeddings might exist
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        # Avoid division by zero for any zero-vector embeddings
        norms = np.where(norms > 0, norms, 1.0)
        X = X / norms
        
        # Fit DBSCAN with cosine distance
        # Cosine distance in sklearn: 1 - cosine_similarity(u, v)
        # For L2-normalized vectors: cosine_distance = 1 - dot(u, v)
        db = DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
        labels = db.fit_predict(X)
        
        # Compute cluster mean embeddings for consistency verification (outlier detection)
        cluster_means = {}
        unique_labels = set(labels)
        for label in unique_labels:
            if label == -1:
                continue  # Outliers don't have a shared cluster mean
            idxs = np.where(labels == label)[0]
            cluster_embs = X[idxs]
            mean_emb = np.mean(cluster_embs, axis=0)
            norm = np.linalg.norm(mean_emb)
            if norm > 0:
                mean_emb = mean_emb / norm
            cluster_means[label] = mean_emb
            
        # We need a clean mapping for UI
        # DBSCAN labels -1 as noise (outliers).
        # In our yearbook app, it's better to assign each outlier face its own unique cluster ID,
        # so the user sees them as individual people cards and can easily name or merge them,
        # rather than grouping all outliers together.
        
        clustered_groups = {}
        updated_faces = []
        
        next_noise_id = 1
        
        for idx, face in enumerate(faces_metadata):
            label = int(labels[idx])
            
            # Copy to avoid mutating original dictionary in-place
            face_copy = face.copy()
            
            # Verify face consistency if it belongs to a cluster
            face_copy["is_suspicious"] = False
            face_copy["similarity"] = 1.0
            
            if label != -1 and label in cluster_means:
                emb = X[idx]
                mean_emb = cluster_means[label]
                # Cosine similarity for L2-normalized vectors is just the dot product
                sim = float(np.dot(emb, mean_emb))
                face_copy["similarity"] = sim
                # If similarity is below 0.48, mark as suspicious (outlier)
                if sim < 0.48:
                    face_copy["is_suspicious"] = True
            
            # We don't need to send the large embedding vector to the frontend to keep payloads small
            if "embedding" in face_copy:
                del face_copy["embedding"]
            
            if label == -1:
                # Assign unique ID to noise face
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
                    "faces": []
                }
            clustered_groups[cluster_id]["faces"].append(face_copy)
            
        # Sort groups by size (descending) so the most frequent faces appear first in UI!
        sorted_groups = sorted(clustered_groups.values(), key=lambda g: len(g["faces"]), reverse=True)
        
        # Re-map into a dictionary with sorted order or just return the list/dict
        sorted_groups_dict = {g["cluster_id"]: g for g in sorted_groups}
        
        return updated_faces, sorted_groups_dict

    @staticmethod
    def auto_tune_epsilon(faces_metadata):
        """
        Runs multi-step search on DBSCAN epsilon to find the optimal face clustering value.
        Scores each eps using a custom Face Clustering Quality Score (FCQS).
        
        Args:
            faces_metadata (list): List of face dicts containing "embedding".
            
        Returns:
            float: Optimal epsilon value.
        """
        if not faces_metadata or len(faces_metadata) < 2:
            return 0.42  # default fallback
            
        eps_candidates = [0.32, 0.36, 0.40, 0.44, 0.48, 0.52, 0.56]
        best_eps = 0.42
        best_score = -1.0
        
        total_count = len(faces_metadata)
        
        for eps in eps_candidates:
            # Extracted embeddings
            embeddings = [face["embedding"] for face in faces_metadata]
            X = np.array(embeddings, dtype=np.float64)
            norms = np.linalg.norm(X, axis=1, keepdims=True)
            norms = np.where(norms > 0, norms, 1.0)
            X = X / norms
            
            db = DBSCAN(eps=eps, min_samples=2, metric="cosine")
            labels = db.fit_predict(X)
            
            unique_labels = set(labels)
            
            # Count size of each group and noise
            cluster_means = {}
            for label in unique_labels:
                if label == -1:
                    continue
                idxs = np.where(labels == label)[0]
                cluster_embs = X[idxs]
                mean_emb = np.mean(cluster_embs, axis=0)
                norm = np.linalg.norm(mean_emb)
                if norm > 0:
                    mean_emb = mean_emb / norm
                cluster_means[label] = mean_emb
                
            clustered_count = 0
            suspicious_count = 0
            noise_count = 0
            
            for idx, label in enumerate(labels):
                if label == -1:
                    noise_count += 1
                else:
                    clustered_count += 1
                    # Check if suspicious (using threshold 0.48)
                    emb = X[idx]
                    mean_emb = cluster_means[label]
                    sim = float(np.dot(emb, mean_emb))
                    if sim < 0.48:
                        suspicious_count += 1
            
            # Formulate the quality score:
            # 1. Clustered ratio (fraction of faces clustered in size >= 2 groups)
            f_clustered = clustered_count / total_count
            
            # 2. Purity (percentage of clustered faces that are not suspicious)
            f_purity = 1.0 - (suspicious_count / (clustered_count + 1e-5))
            
            # 3. Noise penalty (some noise is expected, but too much noise is penalized)
            f_noise = noise_count / total_count
            
            # Combined Quality Score
            score = f_clustered * f_purity * (1.0 - 0.5 * f_noise)
            
            print(f"[Auto-Tune] eps={eps:.2f}: clustered={clustered_count}/{total_count}, suspicious={suspicious_count}, noise={noise_count}, score={score:.4f}")
            
            if score > best_score:
                best_score = score
                best_eps = eps
                
        print(f"[Auto-Tune] Completed. Best eps={best_eps:.2f} with score={best_score:.4f}")
        return best_eps
