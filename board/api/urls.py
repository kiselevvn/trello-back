# api/urls_alternative.py (если нужны явные пути)
from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenVerifyView
from . import views_auth
# (
#     RegisterView, CustomTokenObtainPairView, CustomTokenRefreshView,
#     LogoutView, LogoutAllView, UserProfileView, ChangePasswordView,
#     VerifyTokenView, UserListView, UserDetailView, LoginView
# )
urlpatterns = [
    
    # Аутентификация
    path('auth/register/', views_auth.RegisterView.as_view(), name='register'),
    path('auth/login/', views_auth.LoginView.as_view(), name='login'),
    path('auth/token/', views_auth.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', views_auth.CustomTokenRefreshView.as_view(), name='token_refresh'),
    # path('auth/token/verify/', views_auth.TokenVerifyView.as_view(), name='token_verify'),
    path('auth/logout/', views_auth.LogoutView.as_view(), name='logout'),
    path('auth/logout-all/', views_auth.LogoutAllView.as_view(), name='logout_all'),
    
    # === Boards ===
    path('boards/', views.BoardViewSet.as_view({'get': 'list', 'post': 'create'}), name='board-list'),
    path('boards/<int:pk>/', views.BoardViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='board-detail'),
    path('boards/<int:pk>/statistics/', views.BoardViewSet.as_view({'get': 'statistics'}), name='board-statistics'),
    path('boards/<int:pk>/activities/', views.BoardViewSet.as_view({'get': 'activities'}), name='board-activities'),
    
    # Board members
    path('boards/<int:board_id>/members/', views.BoardMembersAPIView.as_view(), name='board-members'),
    path('boards/<int:board_id>/members/add/', views.BoardMembersAPIView.as_view(), name='board-members-add'),
    path('boards/<int:board_id>/members/remove/', views.BoardMembersAPIView.as_view(), name='board-members-remove'),
    
    # === Columns ===
    path('columns/', views.ColumnViewSet.as_view({'get': 'list', 'post': 'create'}), name='column-list'),
    path('columns/<int:pk>/', views.ColumnViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='column-detail'),
    path('columns/<int:pk>/move/', views.ColumnViewSet.as_view({'patch': 'move'}), name='column-move'),
    
    # Board columns
    path('boards/<int:board_id>/columns/', views.ColumnViewSet.as_view({'get': 'list'}), name='board-columns'),
    
    # === Tasks ===
    path('tasks/', views.TaskViewSet.as_view({'get': 'list', 'post': 'create'}), name='task-list'),
    path('tasks/<int:pk>/', views.TaskViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='task-detail'),
    path('tasks/<int:pk>/move/', views.TaskViewSet.as_view({'patch': 'move'}), name='task-move'),
    path('tasks/<int:pk>/archive/', views.TaskViewSet.as_view({'post': 'archive'}), name='task-archive'),
    path('tasks/<int:pk>/restore/', views.TaskViewSet.as_view({'post': 'restore'}), name='task-restore'),
    
    # Column tasks
    path('columns/<int:column_id>/tasks/', views.TaskViewSet.as_view({'get': 'list'}), name='column-tasks'),
    
    # === Comments ===
    path('comments/', views.CommentViewSet.as_view({'get': 'list', 'post': 'create'}), name='comment-list'),
    path('comments/<int:pk>/', views.CommentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='comment-detail'),
    
    # Task comments
    path('tasks/<int:task_id>/comments/', views.CommentViewSet.as_view({'get': 'list'}), name='task-comments'),
    
    # === Attachments ===
    path('attachments/', views.AttachmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='attachment-list'),
    path('attachments/<int:pk>/', views.AttachmentViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'}), name='attachment-detail'),
    
    # Task attachments
    path('tasks/<int:task_id>/attachments/', views.AttachmentViewSet.as_view({'get': 'list'}), name='task-attachments'),
    
    # === Labels ===
    path('labels/', views.LabelViewSet.as_view({'get': 'list', 'post': 'create'}), name='label-list'),
    path('labels/<int:pk>/', views.LabelViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='label-detail'),
    
    # Board labels
    path('boards/<int:board_id>/labels/', views.LabelViewSet.as_view({'get': 'list'}), name='board-labels'),
    
    # === Users ===
    path('users/', views.UserViewSet.as_view({'get': 'list'}), name='user-list'),
    path('users/me/', views.UserViewSet.as_view({'get': 'me'}), name='user-me'),
    path('users/tasks-statistics/', views.UserViewSet.as_view({'get': 'tasks_statistics'}), name='user-tasks-statistics'),
    
    # === Activities ===
    path('activities/', views.ActivityLogViewSet.as_view({'get': 'list'}), name='activity-list'),
    path('activities/<int:pk>/', views.ActivityLogViewSet.as_view({'get': 'retrieve'}), name='activity-detail'),
]