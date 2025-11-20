# core_passport/urls.py

from django.urls import path
from .views import (
    MintPassportAPIView, 
    PassportDetailView, 
    UniversalWipeInterfaceView, 
    local_wipe_and_mint,
    remote_file_delete # <-- NEW
)

urlpatterns = [
    # API Endpoints
    path('mint/', MintPassportAPIView.as_view(), name='mint-passport'),
    path('mint/local-wipe-and-mint/', local_wipe_and_mint, name='local-wipe-and-mint'),
    path('delete-files/', remote_file_delete, name='remote-file-delete'), # <-- NEW
    
    # UI/Viewer Endpoints
    path('interface/', UniversalWipeInterfaceView, name='wipe-interface'),
    path('view/<str:imei_serial>/', PassportDetailView.as_view(), name='passport-detail'),
]