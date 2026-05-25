// Application State
const state = {
    clusteredGroups: {},
    activeGroup: null,
    sourceDir: "",
    exportDir: "",
    sensitivity: 1.12,
    statusInterval: null,
    activeFaceData: null, // Cache details of face currently viewed in lightbox
    wizardActive: false,
    wizardIndex: 0,
    wizardGroups: []
};

// DOM Elements
const elements = {
    sourceDirInput: document.getElementById('source-dir'),
    exportDirInput: document.getElementById('export-dir'),
    btnScan: document.getElementById('btn-scan'),
    btnExport: document.getElementById('btn-export'),
    btnCreateSamples: document.getElementById('btn-create-samples'),
    sensitivitySlider: document.getElementById('sensitivity-slider'),
    sensitivityValue: document.getElementById('sensitivity-value'),
    configClustering: document.getElementById('config-clustering'),
    configExport: document.getElementById('config-export'),
    configNaming: document.getElementById('config-naming'),
    btnWizard: document.getElementById('btn-wizard'),
    exportThresholdSlider: document.getElementById('export-threshold-slider'),
    exportThresholdValue: document.getElementById('export-threshold-value'),
    exportExcludeCheckbox: document.getElementById('export-exclude-checkbox'),
    btnChooseSourceDir: document.getElementById('btn-choose-source'),
    btnChooseExportDir: document.getElementById('btn-choose-export'),
    exportStructureSelect: document.getElementById('export-structure'),
    sensitivityExplain: document.getElementById('sensitivity-explain'),
    visNode1: document.getElementById('vis-node-1'),
    visNode2: document.getElementById('vis-node-2'),
    visNode3: document.getElementById('vis-node-3'),
    visNode4: document.getElementById('vis-node-4'),
    structurePreview: document.getElementById('structure-preview'),
    
    // Header Stats
    appStatusBadge: document.getElementById('app-status-badge'),
    appStatusText: document.getElementById('app-status-text'),
    statTotalPhotos: document.getElementById('stat-total-photos'),
    statTotalFaces: document.getElementById('stat-total-faces'),
    statTotalPeople: document.getElementById('stat-total-people'),
    
    // Panels
    emptyState: document.getElementById('empty-state'),
    scanProgressPanel: document.getElementById('scan-progress-panel'),
    resultsGridPanel: document.getElementById('results-grid-panel'),
    peopleGrid: document.getElementById('people-grid'),
    
    // Progress Card
    progressTitle: document.getElementById('progress-title'),
    progressFile: document.getElementById('progress-file'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    progressCount: document.getElementById('progress-count'),
    progressFaces: document.getElementById('progress-faces'),
    
    // Modal (Group details)
    groupModal: document.getElementById('group-modal'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    modalAvatar: document.getElementById('modal-avatar'),
    modalPersonName: document.getElementById('modal-person-name'),
    modalPhotosCount: document.getElementById('modal-photos-count'),
    modalFacesGallery: document.getElementById('modal-faces-gallery'),
    
    // Naming Wizard Modal
    wizardModal: document.getElementById('wizard-modal'),
    wizardCloseBtn: document.getElementById('wizard-close-btn'),
    wizardAvatar: document.getElementById('wizard-avatar'),
    wizardNameInput: document.getElementById('wizard-name-input'),
    wizardFacesGallery: document.getElementById('wizard-faces-gallery'),
    wizardProgressText: document.getElementById('wizard-progress-text'),
    wizardProgressBar: document.getElementById('wizard-progress-bar'),
    wizardBtnPrev: document.getElementById('wizard-btn-prev'),
    wizardBtnSkip: document.getElementById('wizard-btn-skip'),
    wizardBtnNext: document.getElementById('wizard-btn-next'),
    
    // Lightbox (Original BBox)
    imageLightbox: document.getElementById('image-lightbox'),
    lightboxCloseBtn: document.getElementById('lightbox-close-btn'),
    lightboxImage: document.getElementById('lightbox-image'),
    lightboxBbox: document.getElementById('lightbox-bbox'),
    lightboxPhotoName: document.getElementById('lightbox-photo-name'),
    lightboxPhotoPath: document.getElementById('lightbox-photo-path'),
    
    // Confetti
    confettiCanvas: document.getElementById('confetti-canvas'),
    toastContainer: document.getElementById('toast-container')
};

// --- Toast System ---
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '';
    if (type === 'success') {
        icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:20px;height:20px;color:#10b981"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    } else if (type === 'error') {
        icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:20px;height:20px;color:#ec4899"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else {
        icon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:20px;height:20px;color:#6366f1"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }
    
    toast.innerHTML = `${icon}<span>${message}</span>`;
    elements.toastContainer.appendChild(toast);
    
    // Remove toast after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'toast-slide-in 0.3s ease reverse forwards';
        setTimeout(() => {
            if (toast.parentNode) {
                elements.toastContainer.removeChild(toast);
            }
        }, 300);
    }, 4000);
}

// --- Debounce Function ---
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// --- Initialize Event Listeners ---
function initEvents() {
    elements.btnScan.addEventListener('click', startScanning);
    elements.btnExport.addEventListener('click', exportResults);
    
    // Debounced slider matching
    elements.sensitivitySlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        state.sensitivity = val;
        elements.sensitivityValue.textContent = val.toFixed(2);
        updateSensitivityVisualizer(val);
        debouncedCluster(val);
    });
    
    // Modal closing
    elements.modalCloseBtn.addEventListener('click', closeModal);
    elements.groupModal.querySelector('.modal-backdrop').addEventListener('click', closeModal);
    
    // Lightbox closing
    elements.lightboxCloseBtn.addEventListener('click', closeLightbox);
    elements.imageLightbox.querySelector('.lightbox-backdrop').addEventListener('click', closeLightbox);
    
    // Name renaming from modal
    elements.modalPersonName.addEventListener('blur', savePersonName);
    elements.modalPersonName.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.target.blur(); // Triggers blur event to save
        }
    });
    
    // Wizard closing & button actions
    elements.wizardCloseBtn.addEventListener('click', closeWizard);
    elements.wizardModal.querySelector('.modal-backdrop').addEventListener('click', closeWizard);
    elements.wizardBtnPrev.addEventListener('click', prevWizard);
    elements.wizardBtnSkip.addEventListener('click', skipWizard);
    elements.wizardBtnNext.addEventListener('click', saveAndNextWizard);
    
    elements.wizardNameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            saveAndNextWizard();
        } else if (e.key === 'Escape') {
            closeWizard();
        }
    });
    
    // Sidebar wizard trigger button
    elements.btnWizard.addEventListener('click', startNamingWizard);
    
    // Re-calculate lightbox bounding box on image load or resize
    elements.lightboxImage.addEventListener('load', alignLightboxBbox);
    window.addEventListener('resize', alignLightboxBbox);
    
    // Create Sample Photos button
    elements.btnCreateSamples.addEventListener('click', createSamplePhotos);
    
    // Export threshold slider label update
    if (elements.exportThresholdSlider) {
        elements.exportThresholdSlider.addEventListener('input', (e) => {
            elements.exportThresholdValue.textContent = `${e.target.value} mặt`;
        });
    }
    
    // Directory chooser actions via Tkinter backend
    if (elements.btnChooseSourceDir) {
        elements.btnChooseSourceDir.addEventListener('click', () => chooseDirectory(elements.sourceDirInput));
    }
    if (elements.btnChooseExportDir) {
        elements.btnChooseExportDir.addEventListener('click', () => chooseDirectory(elements.exportDirInput));
    }
    
    // Export structure select visualizer change
    if (elements.exportStructureSelect) {
        elements.exportStructureSelect.addEventListener('change', (e) => {
            updateStructureVisualizer(e.target.value);
        });
    }
    
    // Initialize Visualizers
    updateSensitivityVisualizer(parseFloat(elements.sensitivitySlider.value));
    updateStructureVisualizer(elements.exportStructureSelect.value);
}

// --- Face Scanning Operations ---
function startScanning() {
    const srcDir = elements.sourceDirInput.value.trim();
    if (!srcDir) {
        showToast("Vui lòng nhập đường dẫn thư mục ảnh gốc.", "error");
        return;
    }
    
    state.sourceDir = srcDir;
    
    // Update UI states
    elements.btnScan.disabled = true;
    elements.emptyState.classList.add('hidden');
    elements.resultsGridPanel.classList.add('hidden');
    elements.scanProgressPanel.classList.remove('hidden');
    
    elements.appStatusBadge.className = 'status-badge scanning';
    elements.appStatusText.textContent = 'Đang quét ảnh...';
    
    // Trigger Scan API
    fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_dir: srcDir })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || "Không thể quét thư mục."); });
        }
        return res.json();
    })
    .then(data => {
        showToast("Bắt đầu tiến trình phân tích ảnh kỷ yếu...", "info");
        // Start polling status
        state.statusInterval = setInterval(pollScanStatus, 500);
    })
    .catch(err => {
        showToast(err.message, "error");
        resetToIdle();
    });
}

function pollScanStatus() {
    fetch('/api/scan-status')
    .then(res => res.json())
    .then(status => {
        if (status.status === 'scanning') {
            const total = status.total_files;
            const processed = status.processed_files;
            const pct = total > 0 ? (processed / total) * 100 : 0;
            
            elements.progressTitle.textContent = total > 0 ? `Đang xử lý ảnh (${Math.round(pct)}%)` : "Đang phân tích thư mục...";
            elements.progressFile.textContent = status.current_file || "...";
            elements.progressBarFill.style.width = `${pct}%`;
            elements.progressCount.textContent = `Đã xử lý: ${processed}/${total} ảnh`;
            elements.progressFaces.textContent = `Đã tìm thấy: ${status.faces_found} khuôn mặt`;
            
            // Stats headers
            elements.statTotalPhotos.textContent = total;
            elements.statTotalFaces.textContent = status.faces_found;
        } 
        else if (status.status === 'done') {
            clearInterval(state.statusInterval);
            showToast(`Hoàn tất! Đã xử lý toàn bộ ảnh và tìm thấy ${status.faces_found} khuôn mặt.`, "success");
            
            // Enable configurations
            elements.configNaming.style.opacity = '1';
            elements.configNaming.style.pointerEvents = 'auto';
            elements.configClustering.style.opacity = '1';
            elements.configClustering.style.pointerEvents = 'auto';
            elements.configExport.style.opacity = '1';
            elements.configExport.style.pointerEvents = 'auto';
            
            elements.btnScan.disabled = false;
            elements.scanProgressPanel.classList.add('hidden');
            
            elements.appStatusBadge.className = 'status-badge done';
            elements.appStatusText.textContent = 'Hoàn thành phân loại';
            
            // Fetch initial clustered groups and prompt for Naming Wizard
            fetchClusters(state.sensitivity, true);
        }
        else if (status.status === 'error') {
            clearInterval(state.statusInterval);
            showToast(status.error_message, "error");
            resetToIdle();
        }
    })
    .catch(err => {
        clearInterval(state.statusInterval);
        showToast("Lỗi khi kết nối với máy chủ.", "error");
        resetToIdle();
    });
}

function resetToIdle() {
    elements.btnScan.disabled = false;
    elements.scanProgressPanel.classList.add('hidden');
    elements.emptyState.classList.remove('hidden');
    elements.appStatusBadge.className = 'status-badge';
    elements.appStatusText.textContent = 'Sẵn sàng phân loại';
    
    // Disable config panels
    elements.configNaming.style.opacity = '0.5';
    elements.configNaming.style.pointerEvents = 'none';
    elements.configClustering.style.opacity = '0.5';
    elements.configClustering.style.pointerEvents = 'none';
    elements.configExport.style.opacity = '0.5';
    elements.configExport.style.pointerEvents = 'none';
}

// --- Face Clustering Operations ---
const debouncedCluster = debounce((eps) => {
    fetchClusters(eps);
}, 200);

function fetchClusters(eps, triggerWizardAfterFetch = false) {
    elements.appStatusBadge.className = 'status-badge scanning';
    elements.appStatusText.textContent = 'Đang xếp nhóm khuôn mặt...';
    
    fetch(`/api/cluster?eps=${eps}`)
    .then(res => res.json())
    .then(groups => {
        state.clusteredGroups = {};
        groups.forEach(g => {
            state.clusteredGroups[g.cluster_id] = g;
        });
        
        elements.appStatusBadge.className = 'status-badge done';
        elements.appStatusText.textContent = 'Đã cập nhật phân loại';
        
        // Update stats
        elements.statTotalPeople.textContent = groups.length;
        
        // Render
        renderPeopleGrid();
        
        // If modal is open, refresh active group in-place!
        if (state.activeGroup && state.clusteredGroups[state.activeGroup.cluster_id]) {
            openGroupDetails(state.activeGroup.cluster_id);
        }
        
        // Enable naming config if groups are available
        if (groups.length > 0) {
            elements.configNaming.style.opacity = '1';
            elements.configNaming.style.pointerEvents = 'auto';
        }
        
        // Automatically prompt to start the naming wizard
        if (triggerWizardAfterFetch && groups.length > 0) {
            setTimeout(() => {
                const start = confirm("Phân loại hoàn tất! Bạn có muốn đặt tên lần lượt từng người ngay bây giờ không?");
                if (start) {
                    startNamingWizard();
                }
            }, 500);
        }
    })
    .catch(err => {
        showToast("Không thể phân cụm khuôn mặt.", "error");
    });
}

// --- Render Main Results Grid ---
function renderPeopleGrid() {
    elements.emptyState.classList.add('hidden');
    elements.resultsGridPanel.classList.remove('hidden');
    elements.peopleGrid.innerHTML = '';
    
    const groups = Object.values(state.clusteredGroups);
    
    if (groups.length === 0) {
        elements.peopleGrid.innerHTML = '<p class="no-results">Không có khuôn mặt nào được nhận diện.</p>';
        return;
    }
    
    groups.forEach(group => {
        const card = document.createElement('div');
        card.className = 'person-card';
        card.dataset.clusterId = group.cluster_id;
        
        // First face crop acts as avatar
        const firstFace = group.faces[0];
        const avatarSrc = firstFace ? firstFace.crop_image : '';
        
        card.innerHTML = `
            <div class="person-avatar-wrapper">
                <img class="person-avatar" src="${avatarSrc}" alt="Avatar">
            </div>
            <div class="person-name-wrapper">
                <span class="person-name" title="${group.person_name}">${group.person_name}</span>
            </div>
            <span class="person-count">${group.faces.length} ảnh</span>
        `;
        
        // Modal open listener
        card.addEventListener('click', () => openGroupDetails(group.cluster_id));
        
        // --- Setup Drag and Drop targets (Drop to merge/move) ---
        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            card.classList.add('drag-over');
        });
        
        card.addEventListener('dragleave', () => {
            card.classList.remove('drag-over');
        });
        
        card.addEventListener('drop', (e) => {
            e.preventDefault();
            card.classList.remove('drag-over');
            
            const faceId = e.dataTransfer.getData('text/plain');
            const targetClusterId = card.dataset.clusterId;
            
            if (faceId && targetClusterId) {
                moveFaceToGroup(faceId, targetClusterId);
            }
        });
        
        elements.peopleGrid.appendChild(card);
    });
}

// --- Detail Modal Operations ---
function openGroupDetails(clusterId) {
    const group = state.clusteredGroups[clusterId];
    if (!group) return;
    
    state.activeGroup = group;
    
    // Set Header details
    const firstFace = group.faces[0];
    elements.modalAvatar.src = firstFace ? firstFace.crop_image : '';
    elements.modalPersonName.value = group.person_name;
    elements.modalPersonName.dataset.clusterId = clusterId;
    elements.modalPhotosCount.textContent = `Xuất hiện trong ${group.faces.length} ảnh gốc`;
    
    // Render Face Gallery
    elements.modalFacesGallery.innerHTML = '';
    group.faces.forEach(face => {
        const faceCard = document.createElement('div');
        faceCard.className = 'face-thumb-card';
        faceCard.draggable = true;
        faceCard.dataset.faceId = face.id;
        
        faceCard.innerHTML = `
            <img class="face-thumb" src="${face.crop_image}" alt="Face Thumbnail">
        `;
        
        // Open original lightbox on click
        faceCard.addEventListener('click', (e) => {
            e.stopPropagation();
            openLightbox(face);
        });
        
        // --- Drag Start for Face Cards ---
        faceCard.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', face.id);
            faceCard.style.opacity = '0.4';
            
            // Highlight all other cards in main grid except this one
            document.querySelectorAll('.person-card').forEach(c => {
                if (c.dataset.clusterId !== clusterId) {
                    c.style.boxShadow = '0 0 10px rgba(99, 102, 241, 0.4)';
                }
            });
        });
        
        faceCard.addEventListener('dragend', () => {
            faceCard.style.opacity = '1';
            document.querySelectorAll('.person-card').forEach(c => {
                c.style.boxShadow = '';
            });
        });
        
        elements.modalFacesGallery.appendChild(faceCard);
    });
    
    elements.groupModal.classList.remove('hidden');
}

function closeModal() {
    elements.groupModal.classList.add('hidden');
    state.activeGroup = null;
}

// --- Renaming Logic ---
function savePersonName(e) {
    const clusterId = e.target.dataset.clusterId;
    const newName = e.target.value.trim();
    
    if (!newName) {
        showToast("Tên người không được để trống.", "error");
        e.target.value = state.clusteredGroups[clusterId].person_name;
        return;
    }
    
    // Save to API
    fetch('/api/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cluster_id: clusterId, new_name: newName })
    })
    .then(res => {
        if (!res.ok) throw new Error("Đổi tên thất bại.");
        return res.json();
    })
    .then(() => {
        showToast(`Đã đổi tên thành "${newName}"`, "success");
        // Update local state
        if (state.clusteredGroups[clusterId]) {
            state.clusteredGroups[clusterId].person_name = newName;
            state.clusteredGroups[clusterId].faces.forEach(f => f.person_name = newName);
        }
        // Re-render
        renderPeopleGrid();
    })
    .catch(err => {
        showToast(err.message, "error");
    });
}

// --- Move / Merge Face via Drag and Drop ---
function moveFaceToGroup(faceId, targetClusterId) {
    const sourceGroup = state.activeGroup;
    if (sourceGroup && sourceGroup.cluster_id === targetClusterId) {
        // Can't drop onto itself
        return;
    }
    
    fetch('/api/move-face', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ face_id: faceId, target_cluster_id: targetClusterId })
    })
    .then(res => {
        if (!res.ok) throw new Error("Chuyển nhóm thất bại.");
        return res.json();
    })
    .then(() => {
        showToast("Đã chuyển khuôn mặt sang nhóm mới thành công.", "success");
        // Fetch new clusters to update everything cleanly
        fetchClusters(state.sensitivity);
    })
    .catch(err => {
        showToast(err.message, "error");
    });
}

// --- Lightbox / Bounding Box Overlay ---
function openLightbox(face) {
    state.activeFaceData = face;
    
    elements.lightboxPhotoName.textContent = face.original_image_name;
    elements.lightboxPhotoPath.textContent = face.original_image;
    
    // Set image source
    elements.lightboxImage.src = `/api/original-photo?path=${encodeURIComponent(face.original_image)}`;
    elements.imageLightbox.classList.remove('hidden');
    
    // Hide bounding box until image finishes loading
    elements.lightboxBbox.style.display = 'none';
}

function alignLightboxBbox() {
    if (!state.activeFaceData) return;
    
    const face = state.activeFaceData;
    const img = elements.lightboxImage;
    
    // Ensure image has loaded and dimensions are calculated
    if (img.naturalWidth === 0 || img.width === 0) return;
    
    const scaleX = img.width / img.naturalWidth;
    const scaleY = img.height / img.naturalHeight;
    
    const [x, y, w, h] = face.bbox;
    
    // Apply scaled CSS coordinates
    elements.lightboxBbox.style.left = `${x * scaleX}px`;
    elements.lightboxBbox.style.top = `${y * scaleY}px`;
    elements.lightboxBbox.style.width = `${w * scaleX}px`;
    elements.lightboxBbox.style.height = `${h * scaleY}px`;
    
    elements.lightboxBbox.style.display = 'block';
}

function closeLightbox() {
    elements.imageLightbox.classList.add('hidden');
    elements.lightboxImage.src = '';
    state.activeFaceData = null;
}

function exportResults() {
    const exportDir = elements.exportDirInput.value.trim();
    if (!exportDir) {
        showToast("Vui lòng nhập đường dẫn thư mục xuất kết quả.", "error");
        return;
    }
    
    const sourceDir = elements.sourceDirInput.value.trim();
    const structureType = elements.exportStructureSelect.value || "flat";
    const groupThreshold = parseInt(elements.exportThresholdSlider.value, 10) || 5;
    const excludeGroups = elements.exportExcludeCheckbox.checked;
    
    elements.btnExport.disabled = true;
    showToast("Đang thực hiện xuất và sắp xếp tệp tin ảnh...", "info");
    
    fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            export_dir: exportDir,
            source_dir: sourceDir,
            structure_type: structureType,
            group_threshold: groupThreshold,
            exclude_groups_from_individuals: excludeGroups
        })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || "Không thể xuất ảnh."); });
        }
        return res.json();
    })
    .then(summary => {
        elements.btnExport.disabled = false;
        if (summary.success) {
            showToast(summary.message, "success");
            triggerConfetti();
        } else {
            showToast("Xuất ảnh hoàn tất nhưng có một vài lỗi xảy ra.", "warning");
        }
    })
    .catch(err => {
        elements.btnExport.disabled = false;
        showToast(err.message, "error");
    });
}

// --- Create Sample Photos (Mock Test) ---
function createSamplePhotos() {
    elements.btnCreateSamples.disabled = true;
    showToast("Đang tạo bộ ảnh mẫu kỷ yếu giả lập...", "info");
    
    fetch('/api/create-samples', { method: 'POST' })
    .then(res => {
        if (!res.ok) throw new Error("Không thể tạo ảnh mẫu.");
        return res.json();
    })
    .then(data => {
        elements.btnCreateSamples.disabled = false;
        elements.sourceDirInput.value = data.source_dir;
        elements.exportDirInput.value = data.export_dir;
        showToast(data.message, "success");
    })
    .catch(err => {
        elements.btnCreateSamples.disabled = false;
        showToast(err.message, "error");
    });
}

// --- Custom Offline Canvas Confetti Animation ---
function triggerConfetti() {
    const canvas = elements.confettiCanvas;
    const ctx = canvas.getContext('2d');
    
    // Resize canvas
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    
    const colors = ['#6366f1', '#a855f7', '#ec4899', '#3b82f6', '#10b981', '#f59e0b'];
    const particles = [];
    
    // Spawn 150 particles
    for (let i = 0; i < 150; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height - canvas.height,
            size: Math.random() * 8 + 6,
            color: colors[Math.floor(Math.random() * colors.length)],
            speedX: Math.random() * 4 - 2,
            speedY: Math.random() * 6 + 4,
            rotation: Math.random() * 360,
            rotationSpeed: Math.random() * 4 - 2
        });
    }
    
    let startTime = Date.now();
    
    function animate() {
        const elapsed = Date.now() - startTime;
        if (elapsed > 4000) {
            // Fade out canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            return;
        }
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        particles.forEach(p => {
            // Physics
            p.y += p.speedY;
            p.x += p.speedX;
            p.rotation += p.rotationSpeed;
            
            // Draw
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rotation * Math.PI / 180);
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
            ctx.restore();
            
            // Loop particles back to top if they exit screen early
            if (p.y > canvas.height) {
                p.y = -10;
                p.x = Math.random() * canvas.width;
            }
        });
        
        requestAnimationFrame(animate);
    }
    
    animate();
}

// --- Interactive Naming Wizard Operations ---
function startNamingWizard() {
    const groups = Object.values(state.clusteredGroups);
    if (groups.length === 0) {
        showToast("Không có nhóm người nào để đặt tên.", "error");
        return;
    }
    
    // Close other modals if open
    closeModal();
    closeLightbox();
    
    state.wizardActive = true;
    state.wizardIndex = 0;
    state.wizardGroups = groups;
    
    elements.wizardModal.classList.remove('hidden');
    showWizardStep(0);
}

function showWizardStep(index) {
    if (index < 0 || index >= state.wizardGroups.length) return;
    
    state.wizardIndex = index;
    const group = state.wizardGroups[index];
    
    // Update Header Progress
    const total = state.wizardGroups.length;
    elements.wizardProgressText.textContent = `Người ${index + 1} / ${total}`;
    
    const pct = ((index + 1) / total) * 100;
    elements.wizardProgressBar.style.width = `${pct}%`;
    
    // Avatar and name
    const firstFace = group.faces[0];
    elements.wizardAvatar.src = firstFace ? firstFace.crop_image : '';
    
    // Set value & pre-select text for easy typing over it
    elements.wizardNameInput.value = group.person_name;
    elements.wizardNameInput.dataset.clusterId = group.cluster_id;
    
    // Enable/Disable buttons based on boundaries
    elements.wizardBtnPrev.disabled = index === 0;
    
    // If it's the last person, change "Next" button text to "Hoàn thành"
    if (index === total - 1) {
        elements.wizardBtnNext.innerHTML = `
            Hoàn thành
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
        `;
    } else {
        elements.wizardBtnNext.innerHTML = `
            Lưu & Tiếp theo
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        `;
    }
    
    // Render Faces gallery
    elements.wizardFacesGallery.innerHTML = '';
    group.faces.forEach(face => {
        const img = document.createElement('img');
        img.className = 'wizard-face-thumb';
        img.src = face.crop_image;
        img.alt = 'Face thumbnail';
        elements.wizardFacesGallery.appendChild(img);
    });
    
    // Autofocus input after a slight delay for transition
    setTimeout(() => {
        elements.wizardNameInput.focus();
        elements.wizardNameInput.select();
    }, 100);
}

function saveAndNextWizard() {
    const index = state.wizardIndex;
    const group = state.wizardGroups[index];
    const newName = elements.wizardNameInput.value.trim();
    
    if (!newName) {
        showToast("Tên người không được để trống.", "error");
        elements.wizardNameInput.focus();
        return;
    }
    
    // Save to API
    fetch('/api/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cluster_id: group.cluster_id, new_name: newName })
    })
    .then(res => {
        if (!res.ok) throw new Error("Đổi tên thất bại.");
        return res.json();
    })
    .then(() => {
        // Update local state in group
        group.person_name = newName;
        group.faces.forEach(f => f.person_name = newName);
        if (state.clusteredGroups[group.cluster_id]) {
            state.clusteredGroups[group.cluster_id].person_name = newName;
            state.clusteredGroups[group.cluster_id].faces.forEach(f => f.person_name = newName);
        }
        
        // Re-render main grid
        renderPeopleGrid();
        
        // If modal details are open for this group, update it too
        if (state.activeGroup && state.activeGroup.cluster_id === group.cluster_id) {
            elements.modalPersonName.value = newName;
        }
        
        // Advance or complete
        if (index === state.wizardGroups.length - 1) {
            closeWizard();
            showToast("Tuyệt vời! Đã hoàn thành đặt tên cho tất cả mọi người.", "success");
            triggerConfetti();
        } else {
            showWizardStep(index + 1);
        }
    })
    .catch(err => {
        showToast(err.message, "error");
    });
}

function prevWizard() {
    if (state.wizardIndex > 0) {
        showWizardStep(state.wizardIndex - 1);
    }
}

function skipWizard() {
    if (state.wizardIndex === state.wizardGroups.length - 1) {
        closeWizard();
        showToast("Đã đóng trình đặt tên.", "info");
    } else {
        showWizardStep(state.wizardIndex + 1);
    }
}

function closeWizard() {
    elements.wizardModal.classList.add('hidden');
    state.wizardActive = false;
    state.wizardGroups = [];
}

// --- Directory Chooser Operations ---
function chooseDirectory(targetInput) {
    showToast("Đang mở hộp thoại chọn thư mục...", "info");
    fetch('/api/choose-directory', { method: 'POST' })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || "Không thể chọn thư mục."); });
        }
        return res.json();
    })
    .then(data => {
        if (data.directory) {
            targetInput.value = data.directory;
            showToast(`Đã chọn thư mục: ${data.directory}`, "success");
        } else {
            showToast("Đã huỷ chọn thư mục.", "warning");
        }
    })
    .catch(err => {
        showToast(err.message, "error");
    });
}

// --- Interactive Visualizers Operations ---
function updateSensitivityVisualizer(val) {
    if (!elements.sensitivityExplain) return;
    
    const nodes = [elements.visNode1, elements.visNode2, elements.visNode3, elements.visNode4];
    
    if (val < 0.95) {
        // Low sensitivity: grouped loosely (nodes clustered tightly together, same color)
        elements.sensitivityExplain.textContent = "Gộp rộng (Ít nhóm to, nguy cơ nhầm lẫn cao)";
        elements.sensitivityExplain.style.color = "#f43f5e"; // Pink/Red warning
        
        nodes.forEach((n, idx) => {
            n.style.background = "var(--accent-indigo)";
            n.style.boxShadow = "0 0 10px var(--accent-indigo)";
            // Bring them close
            n.style.transform = `translateX(${(idx - 1.5) * 4}px)`;
        });
    } 
    else if (val >= 0.95 && val <= 1.25) {
        // Balanced sensitivity: optimally clustered (2 colored pairs, medium distance)
        elements.sensitivityExplain.textContent = "Phân nhóm cân bằng (Tối ưu - Khuyến nghị)";
        elements.sensitivityExplain.style.color = "var(--accent-emerald)";
        
        nodes.forEach((n, idx) => {
            if (idx < 2) {
                n.style.background = "var(--accent-indigo)";
                n.style.boxShadow = "0 0 10px var(--accent-indigo)";
                n.style.transform = `translateX(-12px)`;
            } else {
                n.style.background = "var(--accent-pink)";
                n.style.boxShadow = "0 0 10px var(--accent-pink)";
                n.style.transform = `translateX(12px)`;
            }
        });
    } 
    else {
        // High sensitivity: strictly split (4 different colors, spaced far apart)
        elements.sensitivityExplain.textContent = "Phân nhóm nghiêm ngặt (Dễ bị chia tách một người thành nhiều nhóm)";
        elements.sensitivityExplain.style.color = "#f59e0b"; // Orange warning
        
        const colors = ["var(--accent-indigo)", "var(--accent-purple)", "var(--accent-pink)", "var(--accent-emerald)"];
        nodes.forEach((n, idx) => {
            n.style.background = colors[idx];
            n.style.boxShadow = `0 0 10px ${colors[idx]}`;
            n.style.transform = `translateX(${(idx - 1.5) * 20}px)`;
        });
    }
}

function updateStructureVisualizer(type) {
    if (!elements.structurePreview) return;
    
    let treeText = "";
    if (type === "person_first") {
        treeText = `📂 output/\n├── 📂 Nguyễn Văn A/\n│   ├── 📂 Lớp 12A/\n│   │   └── 📄 anh_chan_dung.jpg\n│   └── 📂 Lớp 12B/\n│       └── 📄 anh_nhom.jpg\n└── 📂 Trần Thị B/\n    └── 📂 Lớp 12A/\n        └── 📄 anh_chup_chung.jpg`;
    } else if (type === "subdir_first") {
        treeText = `📂 output/\n├── 📂 Lớp 12A/\n│   ├── 📂 Nguyễn Văn A/\n│   │   └── 📄 anh_chan_dung.jpg\n│   └── 📂 Trần Thị B/\n│       └── 📄 anh_chup_chung.jpg\n└── 📂 Lớp 12B/\n    └── 📂 Nguyễn Văn A/\n        └── 📄 anh_nhom.jpg`;
    } else { // flat
        treeText = `📂 output/\n├── 📂 Nguyễn Văn A/\n│   ├── 📄 anh_chan_dung.jpg\n│   └── 📄 anh_nhom.jpg\n└── 📂 Trần Thị B/\n    └── 📄 anh_chup_chung.jpg`;
    }
    
    elements.structurePreview.textContent = treeText;
}

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initEvents();
});
