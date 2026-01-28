/**
 * FacePass
 * Frontend JavaScript Application
 */

class FaceAuthApp {
    constructor() {
        this.video = null;
        this.regVideo = null;
        this.stream = null;
        this.regStream = null;
        this.canvas = null;
        this.capturedImage = null;
        this.isProcessing = false;
        
        this.init();
    }
    
    init() {
        // Initialize DOM elements
        this.video = document.getElementById('video');
        this.regVideo = document.getElementById('regVideo');
        this.overlay = document.getElementById('overlay');
        this.regOverlay = document.getElementById('regOverlay');
        
        // Bind event listeners
        this.bindEvents();
        
        // Load initial data
        this.loadUsers();
        this.loadTodayAttendance();
        
        // Auto-refresh records every 30 seconds
        setInterval(() => {
            this.loadTodayAttendance();
        }, 30000);
    }
    
    bindEvents() {
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e.target.closest('.nav-tab').dataset.tab));
        });
        
        // Camera placeholders
        document.getElementById('cameraPlaceholder')?.addEventListener('click', () => this.startCamera('attendance'));
        document.getElementById('regCameraPlaceholder')?.addEventListener('click', () => this.startCamera('register'));
        
        // Toggle camera button
        document.getElementById('toggleCamera')?.addEventListener('click', () => this.toggleCamera('attendance'));
        
        // Capture buttons
        document.getElementById('captureBtn')?.addEventListener('click', () => this.captureAndIdentify());
        document.getElementById('captureRegBtn')?.addEventListener('click', () => this.captureForRegistration());
        
        // Registration form
        document.getElementById('registerForm')?.addEventListener('submit', (e) => this.handleRegistration(e));
        
        // Retake photo
        document.getElementById('retakeBtn')?.addEventListener('click', () => this.retakePhoto());
        
        // Refresh records
        document.getElementById('refreshRecords')?.addEventListener('click', () => this.loadTodayAttendance());
    }
    
    switchTab(tabId) {
        // Update nav tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });
        
        // Update content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabId}-tab`);
        });
        
        // Stop cameras when switching tabs
        if (tabId === 'attendance') {
            this.stopCamera('register');
        } else if (tabId === 'register') {
            this.stopCamera('attendance');
        } else {
            this.stopCamera('attendance');
            this.stopCamera('register');
        }
        
        // Reload data for records tab
        if (tabId === 'records') {
            this.loadTodayAttendance();
            this.loadUsers();
        }
    }
    
    async startCamera(mode) {
        try {
            const constraints = {
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                }
            };
            
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            if (mode === 'attendance') {
                this.stream = stream;
                this.video.srcObject = stream;
                document.getElementById('cameraPlaceholder').classList.add('hidden');
                document.getElementById('captureBtn').disabled = false;
            } else {
                this.regStream = stream;
                this.regVideo.srcObject = stream;
                document.getElementById('regCameraPlaceholder').classList.add('hidden');
                document.getElementById('captureRegBtn').disabled = false;
            }
            
        } catch (error) {
            console.error('Camera error:', error);
            this.showToast('Failed to access camera. Please check permissions.', 'error');
        }
    }
    
    stopCamera(mode) {
        if (mode === 'attendance' && this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            this.video.srcObject = null;
            document.getElementById('cameraPlaceholder').classList.remove('hidden');
            document.getElementById('captureBtn').disabled = true;
        } else if (mode === 'register' && this.regStream) {
            this.regStream.getTracks().forEach(track => track.stop());
            this.regStream = null;
            this.regVideo.srcObject = null;
            document.getElementById('regCameraPlaceholder').classList.remove('hidden');
            document.getElementById('captureRegBtn').disabled = true;
        }
    }
    
    toggleCamera(mode) {
        if (mode === 'attendance') {
            if (this.stream) {
                this.stopCamera('attendance');
            } else {
                this.startCamera('attendance');
            }
        }
    }
    
    captureFrame(video) {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        
        // Mirror the image horizontally to match the preview
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0);
        
        return canvas;
    }
    
    async captureAndIdentify() {
        if (this.isProcessing || !this.stream) return;
        
        this.isProcessing = true;
        this.showLoading(true);
        
        try {
            const canvas = this.captureFrame(this.video);
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
            
            const formData = new FormData();
            formData.append('face_image', blob, 'capture.jpg');
            
            const response = await fetch('/api/identify', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            this.displayResult(result);
            
            // Update metrics
            if (result.confidence) {
                this.updateMetric('confidence', result.confidence * 100);
            }
            
            // Refresh attendance records
            if (result.success) {
                this.loadTodayAttendance();
            }
            
        } catch (error) {
            console.error('Identification error:', error);
            this.displayResult({
                success: false,
                message: 'An error occurred during identification'
            });
        } finally {
            this.isProcessing = false;
            this.showLoading(false);
        }
    }
    
    displayResult(result) {
        const container = document.getElementById('resultContainer');
        
        if (result.success) {
            container.innerHTML = `
                <div class="result-success">
                    <div class="result-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                            <polyline points="22 4 12 14.01 9 11.01"/>
                        </svg>
                    </div>
                    <div class="result-title">${result.action === 'punch_in' ? 'Punched In!' : 'Punched Out!'}</div>
                    <div class="result-message">${result.message}</div>
                    <div class="result-details">
                        <div class="result-detail">
                            <div class="result-detail-label">Employee</div>
                            <div class="result-detail-value">${result.user_name || 'Unknown'}</div>
                        </div>
                        <div class="result-detail">
                            <div class="result-detail-label">Time</div>
                            <div class="result-detail-value">${new Date(result.timestamp).toLocaleTimeString()}</div>
                        </div>
                        <div class="result-detail">
                            <div class="result-detail-label">Confidence</div>
                            <div class="result-detail-value">${(result.confidence * 100).toFixed(1)}%</div>
                        </div>
                    </div>
                </div>
            `;
            this.showToast(result.message, 'success');
        } else {
            container.innerHTML = `
                <div class="result-error">
                    <div class="result-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="15" y1="9" x2="9" y2="15"/>
                            <line x1="9" y1="9" x2="15" y2="15"/>
                        </svg>
                    </div>
                    <div class="result-title">Recognition Failed</div>
                    <div class="result-message">${result.message || 'Please try again'}</div>
                </div>
            `;
            if (result.message) {
                this.showToast(result.message, 'error');
            }
        }
    }
    
    captureForRegistration() {
        if (!this.regStream) return;
        
        const canvas = this.captureFrame(this.regVideo);
        this.capturedImage = canvas;
        
        // Show preview
        const preview = document.getElementById('capturedPreview');
        const previewImg = document.getElementById('previewImage');
        previewImg.src = canvas.toDataURL('image/jpeg', 0.9);
        preview.classList.remove('hidden');
        
        // Enable register button
        document.getElementById('registerBtn').disabled = false;
        
        this.showToast('Photo captured! Fill in the details and click Register.', 'success');
    }
    
    retakePhoto() {
        this.capturedImage = null;
        document.getElementById('capturedPreview').classList.add('hidden');
        document.getElementById('registerBtn').disabled = true;
    }
    
    async handleRegistration(e) {
        e.preventDefault();
        
        if (!this.capturedImage) {
            this.showToast('Please capture a photo first', 'error');
            return;
        }
        
        this.showLoading(true);
        
        try {
            const formData = new FormData();
            formData.append('employee_id', document.getElementById('employeeId').value);
            formData.append('name', document.getElementById('employeeName').value);
            formData.append('email', document.getElementById('employeeEmail').value || '');
            formData.append('department', document.getElementById('employeeDept').value || '');
            
            // Convert canvas to blob
            const blob = await new Promise(resolve => 
                this.capturedImage.toBlob(resolve, 'image/jpeg', 0.9)
            );
            formData.append('face_image', blob, 'face.jpg');
            
            const response = await fetch('/api/register', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showToast(`${result.message}`, 'success');
                
                // Reset form
                document.getElementById('registerForm').reset();
                this.retakePhoto();
                
                // Reload users
                this.loadUsers();
                
                // Switch to attendance tab
                setTimeout(() => this.switchTab('attendance'), 1500);
            } else {
                throw new Error(result.detail || result.message || 'Registration failed');
            }
            
        } catch (error) {
            console.error('Registration error:', error);
            this.showToast(error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    async loadUsers() {
        try {
            const response = await fetch('/api/users');
            const users = await response.json();
            
            // Update employee count
            document.getElementById('employeeCount').textContent = users.length;
            
            // Update employees list
            const list = document.getElementById('employeesList');
            
            if (users.length === 0) {
                list.innerHTML = `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/>
                            <circle cx="9" cy="7" r="4"/>
                            <path d="M23 21v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75"/>
                        </svg>
                        <p>No employees registered yet</p>
                    </div>
                `;
                return;
            }
            
            list.innerHTML = users.map(user => `
                <div class="employee-card">
                    <div class="employee-avatar">${user.name.charAt(0).toUpperCase()}</div>
                    <div class="employee-info">
                        <div class="employee-name">${user.name}</div>
                        <div class="employee-id">${user.employee_id}</div>
                    </div>
                    ${user.department ? `<span class="employee-dept">${user.department}</span>` : ''}
                </div>
            `).join('');
            
        } catch (error) {
            console.error('Failed to load users:', error);
        }
    }
    
    async loadTodayAttendance() {
        try {
            const response = await fetch('/api/attendance/today');
            const records = await response.json();
            
            const tbody = document.getElementById('attendanceTableBody');
            
            if (records.length === 0) {
                tbody.innerHTML = `
                    <tr class="empty-row">
                        <td colspan="5">
                            <div class="empty-state">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                    <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                                    <path d="M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2z"/>
                                </svg>
                                <p>No attendance records for today</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = records.map(record => {
                const punchIn = record.punch_in ? new Date(record.punch_in).toLocaleTimeString() : '--';
                const punchOut = record.punch_out ? new Date(record.punch_out).toLocaleTimeString() : '--';
                const statusClass = record.punch_out ? 'checked-out' : 'checked-in';
                
                return `
                    <tr>
                        <td>
                            <strong>${record.user_name}</strong>
                            <div style="font-size: 0.8rem; color: var(--text-muted);">${record.employee_id}</div>
                        </td>
                        <td>${punchIn}</td>
                        <td>${punchOut}</td>
                        <td>
                            <span class="status-badge ${statusClass}">
                                ${record.status}
                            </span>
                        </td>
                        <td>${(record.confidence * 100).toFixed(1)}%</td>
                    </tr>
                `;
            }).join('');
            
        } catch (error) {
            console.error('Failed to load attendance:', error);
        }
    }
    
    updateMetric(type, value) {
        const bar = document.getElementById(`${type}Bar`);
        const valueEl = document.getElementById(`${type}Value`);
        
        if (bar) bar.style.width = `${Math.min(value, 100)}%`;
        if (valueEl) valueEl.textContent = `${value.toFixed(1)}%`;
    }
    
    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        overlay.classList.toggle('hidden', !show);
    }
    
    showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        const toastMessage = toast.querySelector('.toast-message');
        const toastIcon = toast.querySelector('.toast-icon');
        
        toastMessage.textContent = message;
        toast.className = `toast ${type}`;
        
        // Set icon based on type
        toastIcon.innerHTML = type === 'success' 
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 4000);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.faceAuthApp = new FaceAuthApp();
});
