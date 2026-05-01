import { createApp, ref, computed, onMounted, onUnmounted } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js';

const app = createApp({
    setup() {
        const user = ref(null);
        const tickets = ref([]);
        const loading = ref(true);
        const viewMode = ref('kanban');
        const searchQuery = ref('');
        const unreadCount = ref(0);
        const selectedTicket = ref(null);
        
        const statuses = ['Abierto', 'En progreso', 'En revisión', 'Cerrado'];

        // --- AUTH ---
        async function checkAuth() {
            try {
                const res = await fetch('/api/users/me');
                if (res.ok) {
                    user.value = await res.json();
                    await fetchTickets();
                    initWebSocket();
                } else {
                    window.location.href = '/auth/login';
                }
            } catch (err) {
                console.error('Auth check failed', err);
                window.location.href = '/auth/login';
            } finally {
                loading.value = false;
                // Initialize Lucide icons after rendering
                setTimeout(() => lucide.createIcons(), 100);
            }
        }

        async function logout() {
            await fetch('/auth/logout', { method: 'POST' });
            window.location.href = '/auth/login';
        }

        // --- TICKETS ---
        async function fetchTickets() {
            const res = await fetch('/api/tickets');
            if (res.ok) {
                tickets.value = await res.json();
            }
        }

        const filteredTickets = computed(() => {
            if (!searchQuery.value) return tickets.value;
            const q = searchQuery.value.toLowerCase();
            return tickets.value.filter(t => 
                t.title.toLowerCase().includes(q) || 
                t.description.toLowerCase().includes(q)
            );
        });

        function getTicketsByStatus(status) {
            return filteredTickets.value.filter(t => t.status === status);
        }

        // --- KANBAN DRAG & DROP ---
        function onDragStart(event, ticket) {
            event.dataTransfer.setData('ticketId', ticket.id);
            event.dataTransfer.effectAllowed = 'move';
        }

        async function onDrop(event, newStatus) {
            const ticketId = event.dataTransfer.getData('ticketId');
            const ticket = tickets.value.find(t => t.id == ticketId);
            
            if (ticket && ticket.status !== newStatus) {
                const oldStatus = ticket.status;
                ticket.status = newStatus; // Optimistic update

                try {
                    const res = await fetch(`/api/tickets/${ticketId}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ status: newStatus })
                    });
                    if (!res.ok) throw new Error('Update failed');
                } catch (err) {
                    ticket.status = oldStatus; // Rollback
                    alert('Failed to update ticket status');
                }
            }
        }

        // --- REALTIME ---
        let ws = null;
        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'notification') {
                    unreadCount.value++;
                    // Optionally refresh tickets if current user is involved
                    fetchTickets();
                }
            };
            
            ws.onclose = () => {
                console.warn('WS disconnected, retrying in 5s...');
                setTimeout(initWebSocket, 5000);
            };
        }

        // --- HELPERS ---
        function formatDate(dateStr) {
            return new Date(dateStr).toLocaleDateString(undefined, { 
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
            });
        }

        const comments = ref([]);
        const attachments = ref([]);
        const newComment = ref('');
        const userSearchQuery = ref('');
        const userResults = ref([]);

        async function selectTicket(ticket) {
            selectedTicket.value = ticket;
            await fetchComments(ticket.id);
            await fetchAttachments(ticket.id);
        }

        function closeTicket() {
            selectedTicket.value = null;
            comments.value = [];
            attachments.value = [];
            userResults.value = [];
            userSearchQuery.value = '';
        }

        async function fetchComments(ticketId) {
            const res = await fetch(`/api/tickets/${ticketId}/comments`);
            if (res.ok) comments.value = await res.json();
        }

        async function fetchAttachments(ticketId) {
            const res = await fetch(`/api/tickets/${ticketId}/attachments`);
            if (res.ok) attachments.value = await res.json();
        }

        async function postComment() {
            const res = await fetch(`/api/tickets/${selectedTicket.value.id}/comments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ body: newComment.value })
            });
            if (res.ok) {
                newComment.value = '';
                await fetchComments(selectedTicket.value.id);
            }
        }

        async function searchUsers() {
            if (userSearchQuery.value.length < 2) {
                userResults.value = [];
                return;
            }
            const res = await fetch(`/api/users?q=${userSearchQuery.value}`);
            if (res.ok) userResults.value = await res.json();
        }

        async function reassignTicket(userId) {
            const res = await fetch(`/api/tickets/${selectedTicket.value.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assigned_to_id: userId })
            });
            if (res.ok) {
                selectedTicket.value.assigned_to_id = userId;
                userResults.value = [];
                userSearchQuery.value = '';
                await fetchTickets();
            }
        }

        async function uploadFiles(event) {
            const files = event.target.files;
            if (!files.length) return;
            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
            const res = await fetch(`/api/tickets/${selectedTicket.value.id}/attachments`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) await fetchAttachments(selectedTicket.value.id);
        }

        async function deleteAttachment(id) {
            if (!confirm('Are you sure you want to delete this attachment?')) return;
            const res = await fetch(`/api/tickets/attachments/${id}`, { method: 'DELETE' });
            if (res.ok) await fetchAttachments(selectedTicket.value.id);
        }

        async function updateTicketStatus() {
            await fetch(`/api/tickets/${selectedTicket.value.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: selectedTicket.value.status })
            });
            await fetchTickets();
        }

        function toggleNotifications() {
            unreadCount.value = 0;
            alert('You have no new notifications');
        }

        function openCreateModal() {
            alert('New Ticket functionality: This would open a form to create a new ticket.');
        }

        onMounted(() => {
            checkAuth();
        });

        return {
            user, tickets, loading, viewMode, searchQuery, unreadCount, selectedTicket,
            statuses, filteredTickets, getTicketsByStatus,
            comments, attachments, newComment, userSearchQuery, userResults,
            logout, onDragStart, onDrop, formatDate, selectTicket, closeTicket,
            postComment, searchUsers, reassignTicket, uploadFiles, updateTicketStatus, deleteAttachment,
            toggleNotifications, openCreateModal
        };
    }
});

app.mount('#app');
