class CanvasInteractionManager {
    constructor() {
        this.viewport = document.getElementById('canvas-viewport');
        this.svgLayer = document.getElementById('canvas-connections');
        this.isDraggingNode = false;
        this.draggedBlockEl = null;
        this.dragBlockId = null;
        this.dragOffset = { x: 0, y: 0 };

        this.isConnecting = false;
        this.sourceBlockId = null;
        this.tempPathEl = null;

        this.canvasId = null;
        this.connections = [];

        this.onMouseMove = this.handleMouseMove.bind(this);
        this.onMouseUp = this.handleMouseUp.bind(this);

        this.init();
    }

    init() {
        window.addEventListener('canvas-rendered', (e) => {
            this.canvasId = e.detail.canvasId;
            this.connections = [...e.detail.connections];
            this.renderAllConnections();
        });

        this.viewport.addEventListener('mousedown', this.handleMouseDown.bind(this));

        // 연결선 클릭 인터랙션 (좌클릭: AI 융합 제안, 우클릭: 연결 끊기)
        this.svgLayer.addEventListener('click', async (e) => {
            const path = e.target.closest('.connection-path');
            if (!path) return;
            const connId = path.getAttribute('data-connection-id');
            if (confirm("✨ [AI 두 메모 융합]\n이 두 메모를 AI로 합성하여 새로운 인사이트 블록을 도출하시겠습니까?")) {
                try {
                    const res = await fetch(`/api/connections/${connId}/ai-synthesize`, { method: 'POST' });
                    if (!res.ok) throw new Error("AI 융합 실패");
                    const newBlock = await res.json();
                    window.dispatchEvent(new CustomEvent('block-injected', { detail: newBlock }));
                } catch(err) { alert(err.message); }
            }
        });

        this.svgLayer.addEventListener('contextmenu', (e) => {
            const path = e.target.closest('.connection-path');
            if (path) {
                e.preventDefault();
                const connId = path.getAttribute('data-connection-id');
                if (confirm('이 연결선을 끊으시겠습니까?')) {
                    this.deleteConnection(connId, path);
                }
            }
        });
    }

    handleMouseDown(e) {
        if (e.button !== 0) return;
        const connectHandle = e.target.closest('.connect-handle');
        if (connectHandle) {
            e.stopPropagation();
            const blockEl = connectHandle.closest('.memo-card');
            if (!blockEl) return;
            this.isConnecting = true;
            this.sourceBlockId = Number(blockEl.getAttribute('data-block-id'));
            this.createTempPath(e);
            window.addEventListener('mousemove', this.onMouseMove);
            window.addEventListener('mouseup', this.onMouseUp);
            return;
        }

        const dragHandle = e.target.closest('.drag-handle');
        if (dragHandle) {
            if (e.target.closest('button')) return;
            const blockEl = dragHandle.closest('.memo-card');
            if (!blockEl) return;

            this.isDraggingNode = true;
            this.draggedBlockEl = blockEl;
            this.dragBlockId = Number(blockEl.getAttribute('data-block-id'));

            const rect = blockEl.getBoundingClientRect();
            this.dragOffset.x = e.clientX - rect.left;
            this.dragOffset.y = e.clientY - rect.top;
            blockEl.classList.add('is-dragging');

            window.addEventListener('mousemove', this.onMouseMove);
            window.addEventListener('mouseup', this.onMouseUp);
        }
    }

    handleMouseMove(e) {
        if (this.isDraggingNode && this.draggedBlockEl) {
            const vRect = this.viewport.getBoundingClientRect();
            let newX = Math.max(10, e.clientX - vRect.left - this.dragOffset.x);
            let newY = Math.max(10, e.clientY - vRect.top - this.dragOffset.y);
            this.draggedBlockEl.style.left = `${newX}px`;
            this.draggedBlockEl.style.top = `${newY}px`;
            this.updateConnectedPaths(this.dragBlockId);
        }

        if (this.isConnecting && this.tempPathEl) {
            const vRect = this.viewport.getBoundingClientRect();
            const sBlock = document.querySelector(`.memo-card[data-block-id="${this.sourceBlockId}"]`);
            if (!sBlock) return;
            const sPt = this.getBlockAnchorPoint(sBlock, 'right');
            this.tempPathEl.setAttribute('d', this.calculateBezierPath(sPt.x, sPt.y, e.clientX - vRect.left, e.clientY - vRect.top));
        }
    }

    async handleMouseUp(e) {
        window.removeEventListener('mousemove', this.onMouseMove);
        window.removeEventListener('mouseup', this.onMouseUp);

        if (this.isDraggingNode && this.draggedBlockEl) {
            const blockId = this.dragBlockId;
            const finalX = parseFloat(this.draggedBlockEl.style.left) || 0;
            const finalY = parseFloat(this.draggedBlockEl.style.top) || 0;
            this.draggedBlockEl.classList.remove('is-dragging');
            this.isDraggingNode = false;
            this.draggedBlockEl = null;

            window.dispatchEvent(new CustomEvent('node-position-synced', {
                detail: { blockId, x_pos: finalX, y_pos: finalY }
            }));

            fetch(`/api/blocks/${blockId}/position`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x_pos: finalX, y_pos: finalY })
            });
        }

        if (this.isConnecting) {
            this.removeTempPath();
            this.isConnecting = false;
            const targetEl = document.elementFromPoint(e.clientX, e.clientY);
            const targetBlock = targetEl ? targetEl.closest('.memo-card') : null;

            if (targetBlock) {
                const targetBlockId = Number(targetBlock.getAttribute('data-block-id'));
                if (targetBlockId && targetBlockId !== this.sourceBlockId) {
                    await this.createConnectionOnServer(this.sourceBlockId, targetBlockId);
                }
            }
            this.sourceBlockId = null;
        }
    }

    calculateBezierPath(x1, y1, x2, y2) {
        const offset = Math.max(40, Math.abs(x2 - x1) * 0.5);
        return `M ${x1} ${y1} C ${x1 + offset} ${y1}, ${x2 - offset} ${y2}, ${x2} ${y2}`;
    }

    getBlockAnchorPoint(blockEl, side = 'right') {
        const x = parseFloat(blockEl.style.left) || 0;
        const y = parseFloat(blockEl.style.top) || 0;
        const w = blockEl.offsetWidth || 256;
        const h = blockEl.offsetHeight || 120;
        return { x: side === 'right' ? x + w : x, y: y + (h / 2) };
    }

    renderAllConnections() {
        this.svgLayer.querySelectorAll('.connection-path').forEach(p => p.remove());
        this.connections.forEach(conn => this.renderSingleConnection(conn));
    }

    renderSingleConnection(conn) {
        const sBlock = document.querySelector(`.memo-card[data-block-id="${conn.source_block_id}"]`);
        const tBlock = document.querySelector(`.memo-card[data-block-id="${conn.target_block_id}"]`);
        if (!sBlock || !tBlock) return;

        const start = this.getBlockAnchorPoint(sBlock, 'right');
        const end = this.getBlockAnchorPoint(tBlock, 'left');

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', this.calculateBezierPath(start.x, start.y, end.x, end.y));
        path.setAttribute('class', 'connection-path');
        path.setAttribute('data-connection-id', conn.id);
        path.setAttribute('data-source-id', conn.source_block_id);
        path.setAttribute('data-target-id', conn.target_block_id);
        path.setAttribute('marker-end', 'url(#arrow)');
        path.setAttribute('title', '클릭: 두 메모 AI 융합 / 우클릭: 삭제');

        this.svgLayer.appendChild(path);
    }

    updateConnectedPaths(blockId) {
        this.svgLayer.querySelectorAll(`.connection-path[data-source-id="${blockId}"], .connection-path[data-target-id="${blockId}"]`).forEach(path => {
            const sId = path.getAttribute('data-source-id');
            const tId = path.getAttribute('data-target-id');
            const sBlock = document.querySelector(`.memo-card[data-block-id="${sId}"]`);
            const tBlock = document.querySelector(`.memo-card[data-block-id="${tId}"]`);
            if (sBlock && tBlock) {
                const start = this.getBlockAnchorPoint(sBlock, 'right');
                const end = this.getBlockAnchorPoint(tBlock, 'left');
                path.setAttribute('d', this.calculateBezierPath(start.x, start.y, end.x, end.y));
            }
        });
    }

    createTempPath(e) {
        this.removeTempPath();
        const vRect = this.viewport.getBoundingClientRect();
        const sBlock = document.querySelector(`.memo-card[data-block-id="${this.sourceBlockId}"]`);
        if (!sBlock) return;
        const start = this.getBlockAnchorPoint(sBlock, 'right');

        this.tempPathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        this.tempPathEl.setAttribute('class', 'connection-temp-path');
        this.tempPathEl.setAttribute('d', this.calculateBezierPath(start.x, start.y, e.clientX - vRect.left, e.clientY - vRect.top));
        this.svgLayer.appendChild(this.tempPathEl);
    }

    removeTempPath() {
        if (this.tempPathEl) { this.tempPathEl.remove(); this.tempPathEl = null; }
    }

    async createConnectionOnServer(sourceId, targetId) {
        if (this.connections.some(c => c.source_block_id === sourceId && c.target_block_id === targetId)) return;
        try {
            const res = await fetch(`/api/canvases/${this.canvasId}/connections`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_block_id: sourceId, target_block_id: targetId })
            });
            const newConn = await res.json();
            this.connections.push(newConn);
            this.renderSingleConnection(newConn);
            window.dispatchEvent(new CustomEvent('connection-added', { detail: newConn }));
        } catch(err) { alert(err.message); }
    }

    async deleteConnection(connectionId, pathEl) {
        await fetch(`/api/connections/${connectionId}`, { method: 'DELETE' });
        pathEl.remove();
        this.connections = this.connections.filter(c => c.id !== Number(connectionId));
        window.dispatchEvent(new CustomEvent('connection-removed', { detail: { connectionId: Number(connectionId) } }));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.canvasInteractionManager = new CanvasInteractionManager();
});
