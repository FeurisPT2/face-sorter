import numpy as np
from sklearn.cluster import DBSCAN

class FaceClusterer:
    @staticmethod
    def cluster_faces(faces_metadata, eps=1.12, min_samples=1, metric="euclidean"):
        """
        Clusters faces based on their 128-d embeddings using DBSCAN.
        
        Args:
            faces_metadata (list): List of dictionaries containing face metadata and "embedding".
            eps (float): Maximum distance between two samples (threshold). For SFace L2 distance,
                         standard threshold is 1.128.
            min_samples (int): The number of samples in a neighborhood for a point to be considered a core point.
                               Set to 1 so even single faces are grouped.
            metric (str): Distance metric to use ('euclidean' or 'cosine').
            
        Returns:
            list: The updated faces_metadata with a "cluster_id" (str) and "person_name" (str) added.
            dict: A dictionary mapping cluster_id to list of face metadata dicts.
        """
        if not faces_metadata:
            return [], {}
            
        # Extract embeddings
        embeddings = [face["embedding"] for face in faces_metadata]
        X = np.array(embeddings)
        
        # Fit DBSCAN
        db = DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
        labels = db.fit_predict(X)
        
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
