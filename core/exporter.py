import os
import shutil
from pathlib import Path

class FaceExporter:
    @staticmethod
    def export_clusters(cluster_groups, export_dir, group_threshold=5, exclude_groups_from_individuals=False):
        """
        Copies the original photos of each cluster group into organized folders,
        and automatically groups collective/group photos into a separate directory.
        """
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        
        summary = {
            "success": True,
            "total_groups": 0,
            "total_files_copied": 0,
            "total_group_photos": 0,
            "message": "",
            "details": []
        }
        
        # Handle dict or list input
        groups_list = cluster_groups.values() if isinstance(cluster_groups, dict) else cluster_groups
        
        # 1. Count faces per original image to identify group photos
        faces_per_image = {}
        unique_image_paths = {} # Map path string to actual Path object
        for group in groups_list:
            for face in group.get("faces", []):
                img_path_str = face["original_image"]
                img_path = Path(img_path_str)
                unique_image_paths[img_path_str] = img_path
                if img_path_str not in faces_per_image:
                    faces_per_image[img_path_str] = set()
                faces_per_image[img_path_str].add(face["id"])
                
        # Group photos are those where count of detected faces >= group_threshold
        group_photos_paths = {
            img_path_str for img_path_str, face_ids in faces_per_image.items()
            if len(face_ids) >= group_threshold
        }
        
        # 2. Export Group Photos to a dedicated folder if any exist
        if group_photos_paths:
            group_photos_dir = export_dir / "Ảnh tập thể"
            group_photos_dir.mkdir(parents=True, exist_ok=True)
            
            copied_group_photos = 0
            for img_path_str in group_photos_paths:
                orig_img_path = unique_image_paths[img_path_str]
                if not orig_img_path.exists():
                    continue
                    
                dest_file_path = group_photos_dir / orig_img_path.name
                counter = 1
                while dest_file_path.exists():
                    stem = orig_img_path.stem
                    suffix = orig_img_path.suffix
                    dest_file_path = group_photos_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                    
                try:
                    shutil.copy2(orig_img_path, dest_file_path)
                    copied_group_photos += 1
                except Exception as e:
                    print(f"Error copying group photo {orig_img_path}: {e}")
                    summary["success"] = False
            
            summary["total_group_photos"] = copied_group_photos
            
        # 3. Export individual groups
        for group in groups_list:
            person_name = group.get("person_name", "Chưa xác định").strip()
            safe_name = "".join(c for c in person_name if c.isalnum() or c in (" ", "_", "-")).strip()
            if not safe_name:
                safe_name = f"Group_{group.get('cluster_id')}"
                
            group_dir = export_dir / safe_name
            
            copied_in_group = set()
            group_copied_count = 0
            
            for face in group.get("faces", []):
                img_path_str = face["original_image"]
                orig_img_path = Path(img_path_str)
                
                # Check if we should exclude group photos from individual folders
                if exclude_groups_from_individuals and img_path_str in group_photos_paths:
                    continue
                    
                if not orig_img_path.exists():
                    print(f"Original image not found: {orig_img_path}")
                    continue
                    
                if orig_img_path in copied_in_group:
                    continue
                    
                # Ensure the individual folder is created only if we actually copy something
                group_dir.mkdir(parents=True, exist_ok=True)
                
                # Handle filename collisions
                dest_file_path = group_dir / orig_img_path.name
                counter = 1
                while dest_file_path.exists():
                    stem = orig_img_path.stem
                    suffix = orig_img_path.suffix
                    dest_file_path = group_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                try:
                    shutil.copy2(orig_img_path, dest_file_path)
                    copied_in_group.add(orig_img_path)
                    group_copied_count += 1
                except Exception as e:
                    print(f"Error copying {orig_img_path} to {dest_file_path}: {e}")
                    summary["success"] = False
                    
            if group_copied_count > 0:
                summary["total_groups"] += 1
                summary["total_files_copied"] += group_copied_count
                summary["details"].append({
                    "person_name": person_name,
                    "folder_name": safe_name,
                    "photos_count": group_copied_count
                })
                
        # Build friendly response message
        msg_parts = []
        if summary["total_group_photos"] > 0:
            msg_parts.append(f"đã phân loại {summary['total_group_photos']} ảnh vào thư mục 'Ảnh tập thể'")
        if summary["total_files_copied"] > 0:
            msg_parts.append(f"xuất {summary['total_files_copied']} ảnh cá nhân vào {summary['total_groups']} thư mục riêng")
            
        if msg_parts:
            summary["message"] = "Đã xuất thành công: " + ", và ".join(msg_parts) + "."
        else:
            summary["message"] = "Không có ảnh nào được xuất."
            
        return summary
