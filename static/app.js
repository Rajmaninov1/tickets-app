const { createApp, ref, computed, onMounted, onUnmounted } = Vue;

const app = createApp({
    setup() {
        const user = ref(null);
        const tickets = ref([]);
        const loading = ref(true);
        const viewMode = ref('kanban');
        const searchQuery = ref('');
        const unreadCount = ref(0);
        const selectedTicket = ref(null);
        const showCreateModal = ref(false);
        const showNotifications = ref(false);
        const notifications = ref([]);
        
        const sortColumn = ref('updated_at');
        const sortOrder = ref('desc');
        
        const newTicket = ref({
            title: '',
            description: '',
            assigned_to_id: null,
            priority: 'Media',
            status: 'Abierto'
        });

        const priorities = ['Baja', 'Media', 'Alta', 'Urgente'];
        const statuses = ['Abierto', 'En progreso', 'En revisión', 'Cerrado'];

        // --- AUTH ---
        async function checkAuth() {
            try {
                const res = await fetch('/api/users/me');
                if (res.ok) {
                    user.value = await res.json();
                    await fetchTickets();
                    await fetchNotifications();
                    initWebSocket();
                } else {
                    window.location.href = '/auth/login';
                }
            } catch (err) {
                console.error('Auth check failed', err);
                window.location.href = '/auth/login';
            } finally {
                loading.value = false;
                refreshIcons();
            }
        }

        function refreshIcons() {
            setTimeout(() => {
                if (window.lucide) lucide.createIcons();
            }, 100);
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
            let result = [...tickets.value];
            if (searchQuery.value) {
                const q = searchQuery.value.toLowerCase();
                result = result.filter(t => 
                    t.title.toLowerCase().includes(q) || 
                    t.description.toLowerCase().includes(q)
                );
            }
            
            return result.sort((a, b) => {
                let valA = a[sortColumn.value];
                let valB = b[sortColumn.value];
                
                // Handle nested objects (author.name, etc)
                if (sortColumn.value.includes('.')) {
                    const [obj, key] = sortColumn.value.split('.');
                    valA = a[obj] ? a[obj][key] : '';
                    valB = b[obj] ? b[obj][key] : '';
                }

                if (valA < valB) return sortOrder.value === 'asc' ? -1 : 1;
                if (valA > valB) return sortOrder.value === 'asc' ? 1 : -1;
                return 0;
            });
        });

        function sortBy(column) {
            if (sortColumn.value === column) {
                sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn.value = column;
                sortOrder.value = 'asc';
            }
        }

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
            
            ws.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'notification') {
                    unreadCount.value++;
                    await fetchNotifications();
                    await fetchTickets();
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

        async function fetchNotifications() {
            const res = await fetch('/api/notifications?unread_only=true');
            if (res.ok) {
                notifications.value = await res.json();
                unreadCount.value = notifications.value.length;
            }
        }

        async function toggleNotifications() {
            showNotifications.value = !showNotifications.value;
            if (showNotifications.value) {
                await fetchNotifications();
                refreshIcons();
            }
        }

        async function markAsRead(notificationId) {
            const res = await fetch(`/api/notifications/${notificationId}/read`, { method: 'PATCH' });
            if (res.ok) {
                await fetchNotifications();
            }
        }

        function openCreateModal() {
            showCreateModal.value = true;
            newTicket.value = {
                title: '',
                description: '',
                assigned_to_id: null,
                priority: 'Media',
                status: 'Abierto'
            };
            refreshIcons();
        }

        async function createTicket() {
            try {
                const res = await fetch('/api/tickets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newTicket.value)
                });
                if (res.ok) {
                    showCreateModal.value = false;
                    await fetchTickets();
                } else {
                    const data = await res.json();
                    alert(`Error: ${data.detail || 'Failed to create ticket'}`);
                }
            } catch (err) {
                alert('Connection error');
            }
        }

        onMounted(() => {
            checkAuth();
        });

        return {
            user, tickets, loading, viewMode, searchQuery, unreadCount, selectedTicket,
            statuses, priorities, filteredTickets, getTicketsByStatus,
            comments, attachments, newComment, userSearchQuery, userResults,
            showCreateModal, newTicket, showNotifications, notifications,
            sortColumn, sortOrder, sortBy,
            logout, onDragStart, onDrop, formatDate, selectTicket, closeTicket,
            postComment, searchUsers, reassignTicket, uploadFiles, updateTicketStatus, deleteAttachment,
            toggleNotifications, openCreateModal, createTicket, markAsRead
        };
    }
});

app.mount('#app');
