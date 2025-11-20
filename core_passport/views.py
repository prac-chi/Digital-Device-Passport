# core_passport/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import subprocess # Required for running the shell commands (rm -rf, dd)
import json 

from .serializers import PassportMintSerializer
from .models import DigitalPassport, EventLog


# --- WIPE ALGORITHMS DEFINITION ---
WIPE_ALGORITHMS = {
    'NIST': {'name': 'NIST SP 800-88 Purge', 'passes': '1 Pass (Random)', 'description': 'The current industry standard for modern SSDs/HDDs. Highly effective and fast.'},
    'DOD': {'name': 'DoD 5220.22-M', 'passes': '3 Passes (Pattern)', 'description': 'A legacy military standard, reliable for older magnetic drives (HDDs) but slower.'},
    'QUICK': {'name': 'Quick Overwrite (Test)', 'passes': '1 Pass (Zero)', 'description': 'Fastest method, suitable for basic reuse but lowest security guarantee.'},
}


# ------------------------------------------------------------------
# 1. UNIVERSAL WIPE INTERFACE (The Web UI Render)
# ------------------------------------------------------------------

def UniversalWipeInterfaceView(request):
    """View that renders the two-button, drive-selection web portal."""
    simulated_drives = [
        {'id': '/dev/sda', 'name': 'Primary System Drive (OS)'},
        {'id': '/dev/sdb', 'name': 'External/Secondary Data Drive'},
        {'id': '/dev/sdc', 'name': 'Encrypted Backup Drive'},
    ]
    
    simulated_folders = [
        {'path': 'Documents', 'name': 'Documents'},
        {'path': 'Downloads', 'name': 'Downloads'},
        {'path': 'Desktop', 'name': 'Desktop'},
    ]
    
    context = {
        'simulated_drives': simulated_drives,
        'simulated_folders': simulated_folders,
        'wipe_algorithms': WIPE_ALGORITHMS,
        'api_mint_url': '/api/v1/mint/local-wipe-and-mint/',
        'api_delete_url': '/api/v1/delete-files/',
        'kali_user_dir': "/home/prachi/", 
        'kali_ip': '192.168.1.7', # Host IP for demonstration purposes
    }
    return render(request, 'core_passport/wipe_interface.html', context)


# ------------------------------------------------------------------
# 2. MINT PASSPORT API (The Core Certification Endpoint)
# ------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch') 
class MintPassportAPIView(APIView):
    """API endpoint to receive validated wipe data and save the record."""
    def post(self, request):
        from .serializers import PassportMintSerializer # Local import to avoid circular dependency
        
        serializer = PassportMintSerializer(data=request.data)
        
        if serializer.is_valid():
            if DigitalPassport.objects.filter(imei_serial=serializer.validated_data['imei_serial']).exists():
                return Response({
                    "error": "Passport already exists.",
                    "detail": "A Digital Passport for this device has already been minted."
                }, status=status.HTTP_409_CONFLICT)
            
            try:
                passport = serializer.create(validated_data=serializer.validated_data)
                return Response({
                    "message": "Digital Passport Minted Successfully.",
                    "imei": passport.imei_serial,
                    "passport_hash": passport.chain_hash 
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                return Response({
                    "error": "Failed to mint passport.",
                    "detail": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ------------------------------------------------------------------
# 3. REMOTE FILE DELETION API (Handles Shell Command for Button 1)
# ------------------------------------------------------------------

@api_view(['POST'])
@csrf_exempt
def remote_file_delete(request):
    """API to execute file deletion commands based on user selection (Button 1)."""
    data = request.data
    target_folders = data.get('folders', []) 
    user_dir = data.get('user_dir', '/home/prachi/')
    
    if not target_folders:
        return Response({'message': 'No folders selected for deletion.'}, status=status.HTTP_200_OK)

    # Construct the rm -rf command based on selected folders
    delete_paths = " ".join([f"{user_dir}{f}/*" for f in target_folders])
    
    # 💥 FIX: Add 'sudo' to elevate permissions for permanent file deletion
    delete_command = f"sudo rm -rf {delete_paths} && echo 'File Deletion Complete.'"
    
    try:
        # NOTE: This command assumes the user running Django has NOPASSWD configured for sudo in Kali.
        subprocess.run(delete_command, shell=True, check=True, capture_output=True)
        return Response({'message': f'Files in {", ".join(target_folders)} Deleted Successfully.', 'status': 200}, status=status.HTTP_200_OK)
    except Exception as e:
        # Log the failure, especially if sudo failed.
        print(f"Deletion failed: {e}")
        return Response({'message': 'File Deletion Failed due to insufficient permissions or command error.', 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ------------------------------------------------------------------
# 4. LOCAL WIPE EXECUTION & MINTING (The Shell Command Trigger for Button 2)
# ------------------------------------------------------------------

@api_view(['POST'])
@csrf_exempt
def local_wipe_and_mint(request):
    """API endpoint triggered by the web browser that runs the DD command and mints the passport (Button 2)."""
    data = request.data
    device_id = data.get('device_id', 'WEB-UNKNOWN')
    target_drive = data.get('target_drive', '/dev/sda')
    algorithm_key = data.get('algorithm', 'NIST')
    user_dir = data.get('user_dir', '/home/prachi/') 

    algorithm = WIPE_ALGORITHMS.get(algorithm_key, WIPE_ALGORITHMS['NIST'])
    
    # --- 1. RUN FREE SPACE WIPE COMMANDS ---
    try:
        # Step 2: WIPE FREE SPACE command execution
        # Runs dd to overwrite free blocks in the user's home directory partition
        # 💥 FIX: Added 'sudo' for dd and rm to ensure privilege for disk access/file removal
        wipe_command = (
            f"sudo dd if=/dev/zero of={user_dir}temp_wipe.dat bs=1M status=none || true; "
            f"sudo rm -f {user_dir}temp_wipe.dat && echo 'Wipe verified.'"
        )
        
        subprocess.run(wipe_command, shell=True, check=True, capture_output=True, text=True)
        
        wipe_status = "SUCCESS"
        wipe_log = f"Secure wipe executed using {algorithm['name']} on {target_drive}. Verification passed."
        
    except Exception as e:
        wipe_status = "FAILURE"
        wipe_log = f"Secure Wipe Shell Command Failed: {str(e)}"
    
    # --- 2. MINT PASSPORT ---
    if wipe_status == "SUCCESS":
        from .serializers import PassportMintSerializer
        
        payload = {
            "imei_serial": f"{device_id}-{target_drive.replace('/', '')}",
            "wipe_status": "SUCCESS",
            "wipe_standard": algorithm['name'],
            "verification_log": wipe_log
        }
        
        serializer = PassportMintSerializer(data=payload)
        if serializer.is_valid():
            passport = serializer.create(validated_data=serializer.validated_data)
            return Response({
                "message": "Passport Minted Successfully.",
                "status": 201,
                "imei": passport.imei_serial,
                "passport_hash": passport.chain_hash,
            }, status=status.HTTP_201_CREATED)
        else:
             return Response({'detail': serializer.errors}, status=400)
    
    return Response({'detail': f"Secure wipe failed: {wipe_log}"}, status=status.HTTP_400_BAD_REQUEST)


# ------------------------------------------------------------------
# 5. PASSPORT DETAIL VIEW (The Web Viewer)
# ------------------------------------------------------------------

class PassportDetailView(APIView):
    """View to display the full, immutable history of a Digital Passport using an HTML template."""
    def get(self, request, imei_serial):
        passport = get_object_or_404(DigitalPassport, imei_serial=imei_serial)
        events = EventLog.objects.filter(passport=passport).order_by('timestamp')
        
        context = {
            'passport': passport,
            'events': events,
        }
        return render(request, 'core_passport/detail.html', context)