import * as THREE from "three"
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls"
import Stats from "three/examples/jsm/libs/stats.module";
import React from "react";
import { DeviceSelectEvent, FloorSelectEvent, LoadEvent } from "./events";
import { apiFetch } from "../api";
import { Device } from "../hooks";

/**
 * Array containing the names of all layers to request from the server.
 * It is assumed that these layers are stored under the /assets directory and are of the GLTF format (*.gltf or *.glb).
 */
const LAYERS = [
    "floors.glb",
    "exterior-walls.glb",
    "interior-walls.glb",
    "windows.glb",
    "stairs.glb",
    "decoration.glb",
    "glass.glb",
    "egg.glb"
]

const DEVICE_GEOM = new THREE.BoxGeometry(3, 3, 3);
const DEVICE_COLOR = 0xff0000;
const DEVICE_HOVER_GEOM = new THREE.BoxGeometry(4, 4, 4);
const DEVICE_HOVER_COLOR = 0x00aaff;
const DEVICE_SELECTED_GEOM = new THREE.BoxGeometry(4, 4, 4);
const DEVICE_SELECTED_COLOR = 0x00ffaa;


/**
 * Singleton class encapsulating three-js code for creating and rendering the building model in the canvas.
 * Communicates with the rest of the application using events which are targetted at the window.
 */
export default class Graphics {
    private static instance?: Graphics;

    private width = window.innerWidth;
    private height = window.innerHeight;
    private ref: any;

    // Event listeners
    private onReize = () => { this.resize(); };
    private onAnimate = () => { this.animate(); };
    private onPointerMove = (event: PointerEvent) => { this.pointerMove(event); }
    private onPointerDown = (event: PointerEvent) => { this.pointerDown(event); }

    // Window event listeners
    // These event handlers listen to events fired on the window 
    // and change the state of the Three scene accordingly
    private onFloorSelect = (event: Event) => { 
        const e = event as FloorSelectEvent;
        this.setFloor(e.detail.floor);
    }

    // Rendering components
    private camera = new THREE.PerspectiveCamera();
    private scene = new THREE.Scene();
    private deviceScene = new THREE.Scene();
    private renderer = new THREE.WebGLRenderer({powerPreference: "high-performance"});
    private rayCaster = new THREE.Raycaster();
    private clippingPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 100);
    private clock = new THREE.Clock();

    private controls = new OrbitControls(this.camera, this.renderer.domElement);
    private stats = Stats()

    // Attributes used for the selection of devices
    private pointer = { x:0, y:0 };
    private _hoveredDevice?: THREE.Object3D<THREE.Event>;
    private _selectedDevice?: THREE.Object3D<THREE.Event>;
    
    private constructor() {
        console.log("Graphics created");
        
        this.width = window.innerWidth;
        this.height = window.innerHeight;

        this.camera.aspect = this.width/this.height;
        this.camera.updateProjectionMatrix();

        // Renderer setup
        this.renderer.autoClear = false;
        this.renderer.setPixelRatio(2);
        this.renderer.setSize(this.width, this.height);
        this.renderer.setClearColor(0x000000);

    // Controls setup
    // NOTE: Keep target aligned with DEVICE_OFFSET below so devices and model stay registered
    this.controls.target.set(160, 25, -120);
        this.controls.minDistance = 50;
        this.camera.position.set(0, 100, 20)
        this.controls.update();
        
        // Clipping plane setup
        this.renderer.clippingPlanes = [ this.clippingPlane ];
    }

    /**
     * Singleton get instance method
     * @returns The only instance of the Graphics class
     */
    static getInstance() {
        if (this.instance) return this.instance;
        const obj = new this();
        this.instance = obj;
        return obj;
    }

    /**
     * Method to initalise the scene.
     * @returns Promise of model loader. Add .then and .catch to intercept success or failure.
     */
    async init(mountRef: React.MutableRefObject<any>) {
        // Add to dom
        this.ref = mountRef.current;
        this.ref.appendChild(this.stats.dom);
        this.ref.appendChild(this.renderer.domElement);

        // Add event listeners
        window.addEventListener('resize', this.onReize);
        window.addEventListener('pointermove', this.onPointerMove);
        window.addEventListener('pointerdown', this.onPointerDown);

        // Add custom event listeners
        window.addEventListener(FloorSelectEvent.TYPE, this.onFloorSelect);

        // Start animation
        this.onAnimate = () => {
            requestAnimationFrame(this.onAnimate);
            this.animate();
        }
        this.onAnimate();

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xb0b0b0);
        const light = new THREE.DirectionalLight(0xf4f4f4);
        light.position.set(0, 100, 0);
        this.scene.add(ambientLight, light);

        // Load devices (catch error if API is unavailable)
        try {
            const devices = (await apiFetch<Device[]>("/api/devices")).body;
            this.setDevices(devices);
        } catch {}

    // Add ground plane (centered at model/device origin)
    const groundGeom = new THREE.PlaneBufferGeometry(300, 300, 8, 8);
        const groundMat = new THREE.MeshBasicMaterial({color: 0x3f3f3f, side: THREE.DoubleSide});
        const groundPlane = new THREE.Mesh(groundGeom, groundMat);
        groundPlane.rotateX(-Math.PI/2);
        groundPlane.position.set(160, 0.5, -120);
        this.scene.add(groundPlane);

        // Load building model
        const loader = new GLTFLoader();
        const loadLayer = async(fileName: string) => {
            const layer = await loader.loadAsync(`/assets/${fileName}`);
            this.scene.add(layer.scene);
        }

        // Load all layers
        for (const layerName of LAYERS) {
            try {
                await loadLayer(layerName);
            } catch {}
        }

        // Inform the application everything is loaded
        window.dispatchEvent(new LoadEvent());
    }


    /**
     * Method to draw a frame on the canvas
     */
    animate() {
        // Rotate the devices
        const angle = THREE.MathUtils.degToRad(180) * this.clock.getDelta();
        this.deviceScene.children.forEach((child) => {
            const r = child.rotation;
            r.set(r.x + angle, r.y + angle, r.z);
        });

        this.renderer.clear();
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
        this.renderer.render(this.deviceScene, this.camera);
        this.stats.update();
    }

    /**
     * Method called to dispose of resources when this object is no longer required.
     */
    dispose() {
        console.log("Graphics destroyed");
        this.ref.removeChild(this.renderer.domElement);
        this.ref.removeChild(this.stats.dom);

        // Remove event listeners
        window.removeEventListener('resize', this.onReize);
        window.removeEventListener('pointermove', this.onPointerMove);
        window.removeEventListener('pointerdown', this.onPointerDown);
        window.removeEventListener(FloorSelectEvent.TYPE, this.onFloorSelect);
        this.onAnimate = () => { this.animate() };

        // Remove old instance
        Graphics.instance = undefined;
    }


    // Setters
    /**
     * Method moves the clipping plane to hide floors above the given floor number.
     * @param floor Integer representing the floor number
     */
    setFloor(floor: number) {
        // Constants controlling floor height
        const perFloor = 12.5
        const base = 12.5;

        // Clamp floor value
        floor = Math.min(Math.max(floor, 0), 7);

        // Calculate clipping height
        let val = base + perFloor*floor;
        this.clippingPlane.set(this.clippingPlane.normal, val);
    }

    /**
     * Add the given devices to the current scene for rendering
     * @param devices The devices to add to the scene
     */
    setDevices(devices: Device[]) {
        // Stop if devices is empty or undefined
        if (!devices) return;

        // Clear existing devices
        this.deviceScene.clear();

        // Align incoming device coordinates (which are API-space) to the model-space
        // The API subtracts the offset from devices.json on import so positions are relative to (0,0,0).
        // The building GLB and ground plane in this scene are centered around (160, 0, -120).
        // Apply this offset so markers line up with the model and remain stable while orbiting/zooming.
        const DEVICE_OFFSET = new THREE.Vector3(160, 0, -120);

        // Create geometry for each device
        const geom = DEVICE_GEOM;
        for (const device of devices) {
            const mat = new THREE.MeshPhongMaterial({color: DEVICE_COLOR});
            const cube = new THREE.Mesh(geom, mat);
            cube.position.set(
                device.position.x + DEVICE_OFFSET.x,
                device.position.y + DEVICE_OFFSET.y,
                device.position.z + DEVICE_OFFSET.z
            );
            cube.userData = device;
            this.deviceScene.add(cube);
        }

        // Add lighting so the devices look nicer
        const ambientLight = new THREE.AmbientLight(0x404040);
        const light = new THREE.DirectionalLight(0xf4f4f4);
        light.position.set(-100, 100, -100);
        this.deviceScene.add(light, ambientLight);
    }


    // Event listeners
    /**
     * Method to update the size of the canvas and camera when the window changes size.
     */
    private resize() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.camera.aspect = this.width/this.height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.width, this.height)
    }

    /**
     * Method called whenever the pointer moves
     * Checks if we are hovering over a device using raycasts
     * @param event 
     */
    private pointerMove(event: PointerEvent) {
        this.pointer.x = ( event.clientX / window.innerWidth ) * 2 - 1;
        this.pointer.y = - ( event.clientY / window.innerHeight ) * 2 + 1;
        
        // Check if raycast intersects any devices
        this.rayCaster.setFromCamera(this.pointer, this.camera);
        const intersects = this.rayCaster.intersectObjects(this.deviceScene.children, false);
        // If an object is detected, change its color so we can easily see it is being hovered
        if (intersects.length) {
            const device:any = intersects[0].object;
            this.deviceHoverEnter(device);
        } else if (this._hoveredDevice) {
            const device:any = this._hoveredDevice;
            this.deviceHoverExit(device);
        }
    }

    /**
     * Method called whenever a pointer down event occurs on the window.
     * Used to select a device when we click on it
     * @param event 
     */
    private pointerDown(event: PointerEvent) {
        this.pointerMove(event);
        if (this._hoveredDevice && event.button === 0)
            this.devicePointerDown(this._hoveredDevice);
    }

    /**
     * Method called when we hover of a device in three-js
     * @param device The device we are currently hovering over (3D object)
     */
    private deviceHoverEnter(device: any) {
        this._hoveredDevice = device;
        if (device === this._selectedDevice) return;
        device.material.color.set(DEVICE_HOVER_COLOR);
        device.geometry = DEVICE_HOVER_GEOM;
    }

    /**
     * Method called when we stop hovering over a device in three-js
     * @param device The device we are no longer hovering over
     */
    private deviceHoverExit(device: any) {
        this._hoveredDevice = undefined;
        if (device === this._selectedDevice) return;
        device.material.color.set(DEVICE_COLOR);
        device.geometry = DEVICE_GEOM;
    }

    /**
     * Method called whenever we click on a device
     * Selects the device for later use
     * @param device The device we have clicked on
     */
    private devicePointerDown(device: any) {
        // If a new device is selected, we must revert any changes to the previous one
        if (device !== this._selectedDevice && this._selectedDevice) {
            const selectedDevice:any = this._selectedDevice;
            selectedDevice.material.color.set(DEVICE_COLOR);
            selectedDevice.geometry = DEVICE_GEOM;
        }
        this._selectedDevice = device;
        if (device) {
            device.material.color.set(DEVICE_SELECTED_COLOR);
            device.geometry = DEVICE_SELECTED_GEOM;
        }

        // Fire device selected event
        window.dispatchEvent(new DeviceSelectEvent(device.userData.name));
    }
}
