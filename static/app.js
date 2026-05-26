// Application State
const state = {
    clusteredGroups: {},
    activeGroup: null,
    sourceDir: "",
    exportDir: "",
    sensitivity: 0.58,
    workers: 4,
    statusInterval: null,
    scanStartTime: null,
    activeFaceData: null, // Cache details of face currently viewed in lightbox
    wizardActive: false,
    wizardIndex: 0,
    wizardGroups: [],
    activeFilter: "all", // "all", "warnings"
    sortByOption: "size_desc" // "size_desc", "size_asc", "name_asc", "warnings_desc"
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
    btnAutoTune: document.getElementById('btn-auto-tune'),
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
    workersSlider: document.getElementById('workers-slider'),
    workersValue: document.getElementById('workers-value'),
    sensitivityExplain: document.getElementById('sensitivity-explain'),
    visNode1: document.getElementById('vis-node-1'),
    visNode2: document.getElementById('vis-node-2'),
    visNode3: document.getElementById('vis-node-3'),
    visNode4: document.getElementById('vis-node-4'),
    structurePreview: document.getElementById('structure-preview'),
    filterAll: document.getElementById('filter-all'),
    filterWarnings: document.getElementById('filter-warnings'),
    sortBy: document.getElementById('sort-by'),
    
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
    btnPauseScan: document.getElementById('btn-pause-scan'),
    btnPauseText: document.getElementById('btn-pause-text'),
    btnStopScan: document.getElementById('btn-stop-scan'),
    
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
    if (elements.btnPauseScan) {
        elements.btnPauseScan.addEventListener('click', togglePauseScan);
    }
    if (elements.btnStopScan) {
        elements.btnStopScan.addEventListener('click', requestStopScan);
    }
    
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
    
    // Workers slider label update
    if (elements.workersSlider) {
        elements.workersSlider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            state.workers = val;
            elements.workersValue.textContent = val;
        });
    }
    
    // Auto-tune button listener
    if (elements.btnAutoTune) {
        elements.btnAutoTune.addEventListener('click', triggerAutoTune);
    }
    
    // Grid Filter Tabs listeners
    if (elements.filterAll && elements.filterWarnings) {
        elements.filterAll.addEventListener('click', () => {
            elements.filterAll.classList.add('active');
            elements.filterAll.style.background = 'rgba(99, 102, 241, 0.15)';
            elements.filterAll.style.color = 'var(--accent-indigo)';
            
            elements.filterWarnings.classList.remove('active');
            elements.filterWarnings.style.background = 'transparent';
            elements.filterWarnings.style.color = 'var(--text-muted)';
            
            state.activeFilter = 'all';
            renderPeopleGrid();
        });
        
        elements.filterWarnings.addEventListener('click', () => {
            elements.filterWarnings.classList.add('active');
            elements.filterWarnings.style.background = 'rgba(99, 102, 241, 0.15)';
            elements.filterWarnings.style.color = 'var(--accent-indigo)';
            
            elements.filterAll.classList.remove('active');
            elements.filterAll.style.background = 'transparent';
            elements.filterAll.style.color = 'var(--text-muted)';
            
            state.activeFilter = 'warnings';
            renderPeopleGrid();
        });
    }
    
    // Sort dropdown listener
    if (elements.sortBy) {
        elements.sortBy.addEventListener('change', (e) => {
            state.sortByOption = e.target.value;
            renderPeopleGrid();
        });
    }

    // Initialize Visualizers
    updateSensitivityVisualizer(parseFloat(elements.sensitivitySlider.value));
    updateStructureVisualizer(elements.exportStructureSelect.value);
    
    // Dynamically query CPU count to scale workers slider
    fetch('/api/system-info')
    .then(res => res.json())
    .then(info => {
        if (elements.workersSlider) {
            const cpuCount = info.cpu_count;
            elements.workersSlider.max = cpuCount;
            
            // Update hint text dynamically to reflect hardware capabilities
            const hint = elements.workersSlider.nextElementSibling;
            if (hint && hint.classList.contains('slider-hint')) {
                hint.textContent = `Tự động tối ưu hoá cho cấu hình máy của bạn: hỗ trợ từ 1 đến ${cpuCount} luồng song song.`;
            }
            
            // Set dynamic default: half of CPU cores, but at least 4 (capped by cpuCount)
            const defaultVal = Math.min(Math.max(4, Math.floor(cpuCount / 2)), cpuCount);
            elements.workersSlider.value = defaultVal;
            state.workers = defaultVal;
            if (elements.workersValue) {
                elements.workersValue.textContent = defaultVal;
            }
        }
    })
    .catch(err => console.log("System info fetch error:", err));
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
    
    // Record scan start time for speed calculation
    state.scanStartTime = Date.now();
    
    // Read workers setting
    const workersCount = elements.workersSlider ? parseInt(elements.workersSlider.value) : 4;
    
    // Trigger Scan API
    fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_dir: srcDir, workers: workersCount })
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
        if (status.status === 'scanning' || status.status === 'paused') {
            const total = status.total_files;
            const processed = status.processed_files;
            const pct = total > 0 ? (processed / total) * 100 : 0;
            
            // Calculate speed (images per second)
            let speedText = '';
            if (processed > 0 && state.scanStartTime && status.status === 'scanning') {
                const elapsedSec = (Date.now() - state.scanStartTime) / 1000;
                const speed = (processed / elapsedSec).toFixed(1);
                const remaining = total - processed;
                const etaSec = remaining / (processed / elapsedSec);
                const etaMin = Math.floor(etaSec / 60);
                const etaSecRem = Math.floor(etaSec % 60);
                speedText = ` • ${speed} ảnh/giây • ETA: ${etaMin}p${etaSecRem < 10 ? '0' : ''}${etaSecRem}s`;
            } else if (status.status === 'paused') {
                speedText = ` • Đang tạm dừng`;
            }
            
            elements.progressTitle.textContent = status.status === 'paused' ? 'Đang tạm dừng...' : (total > 0 ? `Đang xử lý ảnh (${Math.round(pct)}%)` : "Đang phân tích thư mục...");
            elements.progressFile.textContent = status.current_file || "...";
            elements.progressBarFill.style.width = `${pct}%`;
            elements.progressCount.textContent = `Đã xử lý: ${processed}/${total} ảnh${speedText}`;
            elements.progressFaces.textContent = `Đã tìm thấy: ${status.faces_found} khuôn mặt`;
            
            // Stats headers
            elements.statTotalPhotos.textContent = total;
            elements.statTotalFaces.textContent = status.faces_found;
            
            // Sync play/pause UI
            updatePauseUI(status.status === 'paused');
        } 
        else if (status.status === 'done') {
            clearInterval(state.statusInterval);
            showToast(`Hoàn tất! Đã xử lý toàn bộ ảnh và tìm thấy ${status.faces_found} khuôn mặt.`, "success");
            
            // Enable configurations by removing CSS class that blocks interaction
            elements.configNaming.classList.remove('disabled-before-scan');
            elements.configNaming.style.opacity = '';
            elements.configNaming.style.pointerEvents = '';
            
            elements.configClustering.classList.remove('disabled-before-scan');
            elements.configClustering.style.opacity = '';
            elements.configClustering.style.pointerEvents = '';
            
            elements.configExport.classList.remove('disabled-before-scan');
            elements.configExport.style.opacity = '';
            elements.configExport.style.pointerEvents = '';
            
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

function togglePauseScan() {
    const isCurrentlyPaused = elements.appStatusBadge.classList.contains('paused');
    const endpoint = isCurrentlyPaused ? '/api/scan/resume' : '/api/scan/pause';
    
    fetch(endpoint, { method: 'POST' })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || "Không thể thực hiện yêu cầu."); });
        }
        return res.json();
    })
    .then(data => {
        if (isCurrentlyPaused) {
            showToast("Tiếp tục tiến trình quét...", "success");
            updatePauseUI(false);
        } else {
            showToast("Đang tạm dừng tiến trình quét...", "info");
            updatePauseUI(true);
        }
    })
    .catch(err => {
        showToast(err.message, "error");
    });
}

function updatePauseUI(isPaused) {
    if (!elements.btnPauseScan || !elements.btnPauseText) return;
    
    if (isPaused) {
        if (!elements.appStatusBadge.classList.contains('paused')) {
            elements.appStatusBadge.className = 'status-badge paused';
            elements.appStatusText.textContent = 'Đang tạm dừng';
            elements.btnPauseScan.innerHTML = `
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <span id="btn-pause-text">Tiếp tục</span>
            `;
            elements.btnPauseText = document.getElementById('btn-pause-text');
        }
    } else {
        if (!elements.appStatusBadge.classList.contains('scanning') && elements.appStatusBadge.className !== 'status-badge') {
            elements.appStatusBadge.className = 'status-badge scanning';
            elements.appStatusText.textContent = 'Đang quét ảnh...';
            elements.btnPauseScan.innerHTML = `
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="6" y="4" width="4" height="16"></rect>
                    <rect x="14" y="4" width="4" height="16"></rect>
                </svg>
                <span id="btn-pause-text">Tạm dừng</span>
            `;
            elements.btnPauseText = document.getElementById('btn-pause-text');
        }
    }
}

function requestStopScan() {
    if (confirm("Bạn có chắc chắn muốn kết thúc tiến trình quét hiện tại? Các ảnh đã quét sẽ được gom cụm và hiển thị ngay lập tức.")) {
        fetch('/api/scan/stop', { method: 'POST' })
        .then(res => {
            if (!res.ok) {
                return res.json().then(err => { throw new Error(err.detail || "Không thể dừng tiến trình."); });
            }
            return res.json();
        })
        .then(data => {
            showToast("Đang dừng tiến trình quét, vui lòng chờ các luồng hiện tại đóng...", "info");
        })
        .catch(err => {
            showToast(err.message, "error");
        });
    }
}

function resetToIdle() {
    elements.btnScan.disabled = false;
    elements.scanProgressPanel.classList.add('hidden');
    elements.emptyState.classList.remove('hidden');
    elements.appStatusBadge.className = 'status-badge';
    elements.appStatusText.textContent = 'Sẵn sàng phân loại';
    
    // Reset pause button state
    if (elements.btnPauseScan) {
        elements.btnPauseScan.innerHTML = `
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <rect x="6" y="4" width="4" height="16"></rect>
                <rect x="14" y="4" width="4" height="16"></rect>
            </svg>
            <span id="btn-pause-text">Tạm dừng</span>
        `;
        elements.btnPauseText = document.getElementById('btn-pause-text');
    }
    
    // Disable config panels by adding CSS class back
    elements.configNaming.classList.add('disabled-before-scan');
    elements.configNaming.style.opacity = '';
    elements.configNaming.style.pointerEvents = '';
    
    elements.configClustering.classList.add('disabled-before-scan');
    elements.configClustering.style.opacity = '';
    elements.configClustering.style.pointerEvents = '';
    
    elements.configExport.classList.add('disabled-before-scan');
    elements.configExport.style.opacity = '';
    elements.configExport.style.pointerEvents = '';
}

// --- Face Clustering Operations ---
const debouncedCluster = debounce((eps) => {
    fetchClusters(eps);
}, 200);

function fetchClusters(sensitivity, triggerWizardAfterFetch = false) {
    elements.appStatusBadge.className = 'status-badge scanning';
    elements.appStatusText.textContent = 'Đang xếp nhóm khuôn mặt...';
    
    const eps = (1.0 - sensitivity).toFixed(2);
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
            elements.configNaming.classList.remove('disabled-before-scan');
            elements.configNaming.style.opacity = '';
            elements.configNaming.style.pointerEvents = '';
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

function triggerAutoTune() {
    if (!elements.btnAutoTune) return;
    
    // Disable button to prevent spamming
    elements.btnAutoTune.disabled = true;
    const originalContent = elements.btnAutoTune.innerHTML;
    elements.btnAutoTune.innerHTML = `
        <svg class="btn-icon spinner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;animation:spin-clockwise 1s linear infinite;"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
        Đang tối ưu hóa...
    `;
    
    showToast("Đang phân tích đặc trưng để tìm độ nhạy tốt nhất...", "info");
    
    fetch('/api/auto-tune', { method: 'POST' })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || "Không thể tối ưu hóa."); });
        }
        return res.json();
    })
    .then(data => {
        const optimalSensitivity = data.optimal_sensitivity;
        showToast(`Đã tìm thấy cấu hình tối ưu: Độ nhạy = ${optimalSensitivity.toFixed(2)}`, "success");
        
        // Update slider value and display
        elements.sensitivitySlider.value = optimalSensitivity;
        elements.sensitivityValue.textContent = optimalSensitivity.toFixed(2);
        
        // Update application state
        state.sensitivity = optimalSensitivity;
        
        // Update visualizer nodes
        updateSensitivityVisualizer(optimalSensitivity);
        
        // Re-fetch clusters and refresh UI
        fetchClusters(optimalSensitivity);
    })
    .catch(err => {
        showToast(err.message, "error");
    })
    .finally(() => {
        elements.btnAutoTune.disabled = false;
        elements.btnAutoTune.innerHTML = originalContent;
    });
}

// --- Render Main Results Grid ---
function renderPeopleGrid() {
    elements.emptyState.classList.add('hidden');
    elements.resultsGridPanel.classList.remove('hidden');
    elements.peopleGrid.innerHTML = '';
    
    let groups = Object.values(state.clusteredGroups);
    
    // 1. Filter groups
    if (state.activeFilter === 'warnings') {
        groups = groups.filter(g => g.faces.some(f => f.is_suspicious));
    }
    
    // 2. Sort groups
    groups.sort((a, b) => {
        if (state.sortByOption === 'size_desc') {
            return b.faces.length - a.faces.length;
        } else if (state.sortByOption === 'size_asc') {
            return a.faces.length - b.faces.length;
        } else if (state.sortByOption === 'name_asc') {
            return a.person_name.localeCompare(b.person_name, 'vi', { numeric: true, sensitivity: 'base' });
        } else if (state.sortByOption === 'warnings_desc') {
            const warningsA = a.faces.filter(f => f.is_suspicious).length;
            const warningsB = b.faces.filter(f => f.is_suspicious).length;
            if (warningsA !== warningsB) {
                return warningsB - warningsA;
            }
            return b.faces.length - a.faces.length;
        }
        return 0;
    });
    
    if (groups.length === 0) {
        elements.peopleGrid.innerHTML = '<p class="no-results">Không có nhóm khuôn mặt nào khớp với bộ lọc.</p>';
        return;
    }
    
    groups.forEach(group => {
        const card = document.createElement('div');
        card.className = 'person-card';
        card.dataset.clusterId = group.cluster_id;
        
        // First face crop acts as avatar
        const firstFace = group.faces[0];
        const avatarSrc = firstFace ? firstFace.crop_image : '';
        
        const hasSuspicious = group.faces.some(f => f.is_suspicious);
        const suspiciousCount = group.faces.filter(f => f.is_suspicious).length;
        let alertBadge = '';
        if (hasSuspicious) {
            alertBadge = `
                <div class="person-alert-badge" title="Nhóm này có chứa ${suspiciousCount} khuôn mặt nghi ngờ không khớp" style="display: flex; align-items: center; justify-content: center; gap: 2px; padding: 2px 6px; width: auto; height: 18px; border-radius: 9px; font-size: 9px; font-weight: 700; background: rgba(245, 158, 11, 0.9); box-shadow: 0 0 10px rgba(245, 158, 11, 0.4); border: 1px solid rgba(255, 255, 255, 0.1);">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="width: 9px; height: 9px; color: #fff;">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    </svg>
                    <span style="color: #fff;">${suspiciousCount}</span>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="person-avatar-wrapper">
                <img class="person-avatar" src="${avatarSrc}" alt="Avatar">
                ${alertBadge}
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
        
        let warningBadge = '';
        if (face.is_suspicious) {
            const pct = Math.round((face.similarity || 0) * 100);
            warningBadge = `
                <div class="warning-badge" title="Độ tương đồng thấp (${pct}%) - Có thể nhận diện sai" style="display: flex; align-items: center; gap: 3px; background: rgba(245, 158, 11, 0.95); padding: 2px 6px; border-radius: 8px; font-size: 9px; font-weight: 700; color: #fff; width: auto; height: 18px; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 2px 8px rgba(0,0,0,0.5);">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="width: 9px; height: 9px; color: #fff;">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    </svg>
                    <span>${pct}%</span>
                </div>
            `;
        }
        
        faceCard.innerHTML = `
            <img class="face-thumb" src="${face.crop_image}" alt="Face Thumbnail">
            ${warningBadge}
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
        // Fetch fresh clusters from backend to reflect group merging immediately!
        fetchClusters(state.sensitivity);
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
        const wrapper = document.createElement('div');
        wrapper.className = 'wizard-face-wrapper';
        wrapper.style.position = 'relative';
        
        let warningBadge = '';
        if (face.is_suspicious) {
            const pct = Math.round((face.similarity || 0) * 100);
            warningBadge = `
                <div class="warning-badge small" title="Độ tương đồng thấp (${pct}%)" style="position: absolute; top: -4px; right: -4px; background: rgba(13, 15, 34, 0.95); border: 1px solid #f59e0b; border-radius: 50%; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; z-index: 2; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width: 10px; height: 10px; color: #f59e0b;">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    </svg>
                </div>
            `;
        }
        
        wrapper.innerHTML = `
            <img class="wizard-face-thumb" src="${face.crop_image}" alt="Face thumbnail" style="width: 60px; height: 60px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); object-fit: cover;">
            ${warningBadge}
        `;
        elements.wizardFacesGallery.appendChild(wrapper);
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
    
    // Fetch fresh clusters from backend to reflect group merging done in Wizard immediately!
    fetchClusters(state.sensitivity);
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
    
    if (val < 0.45) {
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
    else if (val >= 0.45 && val <= 0.65) {
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
