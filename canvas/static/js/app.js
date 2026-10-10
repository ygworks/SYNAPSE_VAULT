document.addEventListener('alpine:init', () => {
    Alpine.data('canvasApp', () => ({
        canvases: [],
        currentCanvasId: null,
        currentCanvas: null,
        blocks: [],
        connections: [],
        
        isModalOpen: false,
        isCanvasModalOpen: false,
        activeBlockId: null,
        isSaving: false,
        
        // PIN 잠금 상태
        isLocked: false,
        isLockEnabled: false,
        pinInput: '',
        pinError: '',
        isVerifyingPin: false,

        formData: { title: '', block_type: 'TEXT', content: '', x_pos: 120, y_pos: 120, metadata: {} },
        canvasFormData: { title: '', canvas_type: 'INBOX' },

        selectedFile: null,
        urlInput: '',
        isScraping: false,
        ytUrlInput: '',
        codeLang: 'javascript',
        activePlayingVideos: {},

        async init() {
            window.canvasAppInstance = this;
            this.bindEvents();
            
            // 1. 잠금 상태 확인 후 잠겨있지 않을 때만 캔버스 로딩
            const unlocked = await this.checkAuthStatus();
            if (unlocked) {
                await this.fetchCanvases();
            }
        },

        bindEvents() {
            window.addEventListener('node-position-synced', (e) => {
                const { blockId, x_pos, y_pos } = e.detail;
                const b = this.blocks.find(x => x.id === Number(blockId));
                if (b) { b.x_pos = x_pos; b.y_pos = y_pos; }
            });
            window.addEventListener('connection-added', (e) => {
                if (!this.connections.some(c => c.id === e.detail.id)) this.connections.push(e.detail);
            });
            window.addEventListener('connection-removed', (e) => {
                this.connections = this.connections.filter(c => c.id !== Number(e.detail.connectionId));
            });
            window.addEventListener('block-injected', (e) => {
                this.blocks.push(e.detail);
                this.highlightCodeBlocks();
            });
        },

        // --- 마스터 PIN 인증 및 잠금 제어 ---
        async checkAuthStatus() {
            try {
                const res = await fetch('/api/auth/status');
                const data = await res.json();
                this.isLockEnabled = data.required;
                if (data.required && !data.authenticated) {
                    this.isLocked = true;
                    return false;
                }
                this.isLocked = false;
                return true;
            } catch (err) {
                console.error('인증 상태 확인 실패:', err);
                return true;
            }
        },

        async submitPin() {
            if (!this.pinInput.trim()) return;
            this.isVerifyingPin = true;
            this.pinError = '';
            try {
                const res = await fetch('/api/auth/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pin: this.pinInput.trim() })
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'PIN 번호가 일치하지 않습니다.');
                }
                this.isLocked = false;
                this.pinInput = '';
                await this.fetchCanvases();
            } catch (err) {
                this.pinError = err.message;
            } finally {
                this.isVerifyingPin = false;
            }
        },

        async logout() {
            try {
                await fetch('/api/auth/logout', { method: 'POST' });
                this.isLocked = true;
                this.pinInput = '';
                this.pinError = '';
            } catch (err) {
                console.error(err);
            }
        },

        highlightCodeBlocks() {
            this.$nextTick(() => {
                if (window.Prism) { Prism.highlightAll(); }
            });
        },

        getNodeWidth(block) {
            if (block.block_type === 'MEDIA_EMBED' || block.block_type === 'BOOKMARK') return 320;
            if (block.block_type === 'CODE') return 340;
            return 260;
        },

        formatBytes(bytes) {
            if (!bytes || bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        },

        // --- 캔버스 관리 ---
        async fetchCanvases() {
            try {
                const res = await fetch('/api/canvases');
                if (!res.ok) throw new Error('캔버스 목록 로드 실패');
                this.canvases = await res.json();
                if (this.canvases.length > 0) {
                    await this.loadCanvas(this.canvases[0].id);
                }
            } catch (err) { console.error(err); }
        },

        async loadCanvas(canvasId) {
            this.currentCanvasId = Number(canvasId);
            this.activePlayingVideos = {};
            try {
                const res = await fetch(`/api/canvases/${this.currentCanvasId}/graph`);
                if (!res.ok) throw new Error('캔버스 그래프 로딩 실패');
                const data = await res.json();
                this.currentCanvas = data.canvas;
                this.blocks = data.blocks;
                this.connections = data.connections;

                this.$nextTick(() => {
                    window.dispatchEvent(new CustomEvent('canvas-rendered', {
                        detail: { canvasId: this.currentCanvasId, connections: this.connections }
                    }));
                    this.highlightCodeBlocks();
                });
            } catch (err) { console.error(err); }
        },

        async createCanvas() {
            if (!this.canvasFormData.title.trim()) return alert('캔버스 이름을 입력하세요.');
            try {
                const res = await fetch('/api/canvases', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.canvasFormData)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || '캔버스 생성 실패');
                }
                const newCanvas = await res.json();
                this.canvases.unshift(newCanvas);
                this.isCanvasModalOpen = false;
                this.canvasFormData.title = '';
                await this.loadCanvas(newCanvas.id);
            } catch (err) { alert(err.message); }
        },

        async deleteCurrentCanvas() {
            if (!this.currentCanvasId) return;
            if (!confirm(`'${this.currentCanvas?.title}' 캔버스를 정말 삭제하시겠습니까?\n모든 노드와 연결선, 구글 드라이브 폴더가 함께 삭제됩니다.`)) return;

            try {
                const res = await fetch(`/api/canvases/${this.currentCanvasId}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('캔버스 삭제 실패');

                this.canvases = this.canvases.filter(c => c.id !== this.currentCanvasId);
                if (this.canvases.length > 0) {
                    await this.loadCanvas(this.canvases[0].id);
                } else {
                    this.currentCanvasId = null;
                    this.currentCanvas = null;
                    this.blocks = [];
                    this.connections = [];
                }
            } catch (err) { alert(err.message); }
        },

        async refreshCurrentCanvas() {
            if (this.currentCanvasId) await this.loadCanvas(this.currentCanvasId);
        },

        // --- 구글 드라이브 즉시 백업 ---
        async triggerDriveBackup() {
            try {
                const res = await fetch('/api/system/backup', { method: 'POST' });
                if (!res.ok) throw new Error('백업 요청 실패');
                alert('☁️ Google Drive로 SQLite DB 백업이 백그라운드에서 시작되었습니다!\n구글 드라이브 SynapseCanvas_Storage 폴더를 확인해 보세요.');
            } catch (err) { alert(err.message); }
        },

        onFileChosen(e) {
            const file = e.target.files[0];
            if (!file) return;
            this.selectedFile = file;
            if (!this.formData.title) { this.formData.title = file.name; }
        },

        async handleCanvasFileDrop(e) {
            if (!this.currentCanvasId) return;
            const files = e.dataTransfer.files;
            if (files.length === 0) return;

            const rect = document.getElementById('canvas-viewport').getBoundingClientRect();
            const dropX = e.clientX - rect.left;
            const dropY = e.clientY - rect.top;

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                try {
                    const blockRes = await fetch(`/api/canvases/${this.currentCanvasId}/blocks`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            title: file.name,
                            block_type: 'FILE',
                            x_pos: dropX + (i * 30),
                            y_pos: dropY + (i * 30)
                        })
                    });
                    const block = await blockRes.json();

                    const formData = new FormData();
                    formData.append('file', file);
                    await fetch(`/api/blocks/${block.id}/attachments`, {
                        method: 'POST',
                        body: formData
                    });
                } catch (err) {
                    console.error('파일 드롭 업로드 실패:', err);
                }
            }
            await this.loadCanvas(this.currentCanvasId);
        },

        playVideo(blockId) { this.activePlayingVideos[blockId] = true; },

        parseYoutubeUrl() {
            const url = this.ytUrlInput.trim();
            const idRegex = /(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
            const match = url.match(idRegex);
            if (match) {
                const videoId = match[1];
                let startSeconds = 0;
                const tMatch = url.match(/[?&]t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?|t=(\d+)/);
                if (tMatch) {
                    if (tMatch[4]) {
                        startSeconds = parseInt(tMatch[4], 10);
                    } else {
                        const h = parseInt(tMatch[1] || 0, 10);
                        const m = parseInt(tMatch[2] || 0, 10);
                        const s = parseInt(tMatch[3] || 0, 10);
                        startSeconds = h * 3600 + m * 60 + s;
                    }
                }
                this.formData.metadata = {
                    ...this.formData.metadata,
                    url: url,
                    video_id: videoId,
                    start_seconds: startSeconds
                };
                if (!this.formData.title) this.formData.title = `YouTube: ${videoId}`;
            }
        },

        async scrapeUrlMeta() {
            if (!this.urlInput.trim()) return alert('URL을 입력하세요.');
            this.isScraping = true;
            try {
                const res = await fetch('/api/utilities/scrape-og', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: this.urlInput.trim() })
                });
                const og = await res.json();
                this.formData.title = og.title || this.formData.title || '웹 북마크';
                this.formData.metadata = {
                    ...this.formData.metadata,
                    url: og.url,
                    title: og.title,
                    description: og.description,
                    image: og.image,
                    hostname: og.hostname
                };
            } catch (err) { alert('메타데이터 수집 실패: ' + err.message); }
            finally { this.isScraping = false; }
        },

        copyCode(text) {
            navigator.clipboard.writeText(text);
            alert('코드가 클립보드에 복사되었습니다.');
        },

        async triggerCanvasAiSummary() {
            if (!this.currentCanvasId) return;
            try {
                const res = await fetch(`/api/canvases/${this.currentCanvasId}/ai-summary`, { method: 'POST' });
                if (!res.ok) throw new Error('AI 브리핑 생성 실패');
                const newBlock = await res.json();
                this.blocks.push(newBlock);
            } catch (err) { alert(err.message); }
        },

        async triggerAiTag(blockId) {
            try {
                const res = await fetch(`/api/blocks/${blockId}/ai-tag`, { method: 'POST' });
                if (!res.ok) throw new Error('AI 태깅 실패');
                const updated = await res.json();
                const idx = this.blocks.findIndex(b => b.id === blockId);
                if (idx !== -1) this.blocks[idx] = updated;
            } catch (err) { alert(err.message); }
        },

        openCreateModal() {
            this.activeBlockId = null;
            this.selectedFile = null;
            this.urlInput = '';
            this.ytUrlInput = '';
            this.codeLang = 'javascript';
            this.formData = {
                title: '',
                block_type: 'TEXT',
                content: '',
                x_pos: 200,
                y_pos: 200,
                metadata: {}
            };
            this.isModalOpen = true;
        },

        openEditModal(block) {
            this.activeBlockId = block.id;
            this.selectedFile = null;
            const meta = block.metadata || {};
            this.urlInput = meta.url || '';
            this.ytUrlInput = meta.url || '';
            this.codeLang = meta.language || 'javascript';

            this.formData = {
                title: block.title,
                block_type: block.block_type,
                content: block.content,
                metadata: { ...meta }
            };
            this.isModalOpen = true;
        },

        closeModal() { this.isModalOpen = false; this.selectedFile = null; },

        async saveBlock() {
            if (!this.formData.title) return alert('제목을 입력하세요.');
            if (this.formData.block_type === 'FILE' && !this.activeBlockId && !this.selectedFile) {
                return alert('업로드할 파일을 선택해 주세요.');
            }

            if (this.formData.block_type === 'CODE') {
                this.formData.metadata = { ...this.formData.metadata, language: this.codeLang };
            }

            this.isSaving = true;
            try {
                if (this.activeBlockId) {
                    const res = await fetch(`/api/blocks/${this.activeBlockId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.formData)
                    });
                    const updated = await res.json();
                    const idx = this.blocks.findIndex(b => b.id === this.activeBlockId);
                    if (idx !== -1) this.blocks[idx] = updated;
                } else {
                    const res = await fetch(`/api/canvases/${this.currentCanvasId}/blocks`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.formData)
                    });
                    if (!res.ok) throw new Error('블록 생성 실패');
                    const created = await res.json();

                    if (this.formData.block_type === 'FILE' && this.selectedFile) {
                        const fileData = new FormData();
                        fileData.append('file', this.selectedFile);
                        const upRes = await fetch(`/api/blocks/${created.id}/attachments`, {
                            method: 'POST',
                            body: fileData
                        });
                        if (!upRes.ok) throw new Error('첨부파일 업로드 실패');
                    }
                    await this.loadCanvas(this.currentCanvasId);
                }
                this.closeModal();
                this.highlightCodeBlocks();
            } catch (err) {
                alert(err.message);
            } finally {
                this.isSaving = false;
            }
        },

        async deleteBlock(id) {
            if (!confirm('블록을 삭제하시겠습니까?')) return;
            await fetch(`/api/blocks/${id}`, { method: 'DELETE' });
            this.blocks = this.blocks.filter(b => b.id !== id);
            this.connections = this.connections.filter(c => c.source_block_id !== id && c.target_block_id !== id);
            window.dispatchEvent(new CustomEvent('canvas-rendered', {
                detail: { canvasId: this.currentCanvasId, connections: this.connections }
            }));
        }
    }));
});
