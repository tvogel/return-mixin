#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, render_template
from typing import Dict, List, Callable, Any, Optional
import threading
import time
import asyncio
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Import control modules
from return_mixin import return_mixin
from bwk_onoff import bwk_onoff
from pk_onoff import pk_onoff
from bhkw_onoff import bhkw_onoff
from feed_121517 import feed_121517
from tww_11 import tww_11
import restart_wp_11

@dataclass
class ControllerConfig:
  """Configuration for a control module"""
  name: str
  title: str
  module: Any
  sleep_interval: int = 30
  max_diagnostics: int = 100
  template: str = "control_basic.html"
  control_loop_handler: Optional[Callable] = None

  @property
  def api_path(self) -> str:
    """Generate API path from name"""
    return self.name

  @property
  def route_path(self) -> str:
    """Generate route path from name"""
    return self.name

class ControllerManager:
  """Manages control modules and their common operations"""

  def __init__(self):
    self.controllers: Dict[str, ControllerConfig] = {}
    self.diagnostics: Dict[str, List] = {}
    self.locks: Dict[str, threading.Lock] = {}

  def register_controller(self, config: ControllerConfig):
    """Register a new controller"""
    self.controllers[config.name] = config
    self.diagnostics[config.name] = []
    self.locks[config.name] = threading.Lock()

  def get_diagnostics(self, controller_name: str):
    """Get diagnostics for a controller"""
    with self.locks[controller_name]:
      return self.diagnostics[controller_name].copy()

  def add_diagnostic_entry(self, controller_name: str, entry: Dict):
    """Add a diagnostic entry for a controller"""
    config = self.controllers[controller_name]
    with self.locks[controller_name]:
      self.diagnostics[controller_name].append(entry)
      if len(self.diagnostics[controller_name]) > config.max_diagnostics:
        self.diagnostics[controller_name].pop(0)

  def start_control_loops(self):
    """Start all control loops"""
    for name, config in self.controllers.items():
      if config.control_loop_handler:
        thread = threading.Thread(target=config.control_loop_handler)
      else:
        thread = threading.Thread(target=self._default_control_loop, args=(name,))
      thread.daemon = True
      thread.start()

  def _default_control_loop(self, controller_name: str):
    """Default control loop implementation"""
    config = self.controllers[controller_name]
    while True:
      try:
        diagnostics = config.module.control_loop()

        # Handle different diagnostic formats
        if isinstance(diagnostics, dict):
          if 'timestamp' in diagnostics and controller_name in ['bwk-onoff', 'pk-onoff', 'bhkw-onoff']:
            # For on/off controllers, separate timestamp from data
            timestamp = diagnostics.pop('timestamp')
            entry = {'timestamp': timestamp, 'data': diagnostics}
          else:
            entry = diagnostics
        else:
          entry = diagnostics

        self.add_diagnostic_entry(controller_name, entry)

      except Exception as e:
        print(f"Error in {controller_name} control loop: {e}")

      time.sleep(config.sleep_interval)

# Initialize Flask app and controller manager
app = Flask(__name__)
app.template_folder = 'templates'
app.static_folder = 'static'

controller_manager = ControllerManager()

# Controller configurations
CONTROLLER_CONFIGS = [
  ControllerConfig(
    name="return-mixin",
    title="Return Mix-in",
    module=return_mixin,
    sleep_interval=5,
    template="return_mixin.html"
  ),
  ControllerConfig(
    name="bwk-onoff",
    title="BWK On/Off Control",
    module=bwk_onoff,
    template="onoff_control.html"
  ),
  ControllerConfig(
    name="pk-onoff",
    title="PK On/Off Control",
    module=pk_onoff,
    template="onoff_control.html"
  ),
  ControllerConfig(
    name="bhkw-onoff",
    title="BHKW On/Off Control",
    module=bhkw_onoff,
    template="onoff_control.html"
  ),
  ControllerConfig(
    name="restart-wp-11",
    title="Restart WP 11 Control",
    module=restart_wp_11,
    sleep_interval=5,
    max_diagnostics=1000,
    template="restart_wp_11.html"
  ),
  ControllerConfig(
    name="tww-11",
    title="TWW 11 Control",
    module=tww_11,
    max_diagnostics=1000,
    template="tww_11.html"
  )
]

# Special handling for feed_121517
def feed_121517_control_loop():
  async def combined_loop():
    await feed_121517.setup_mqtt()
    while True:
      diagnostics = feed_121517.control_loop()
      controller_manager.add_diagnostic_entry("feed-121517", diagnostics)
      await asyncio.sleep(30)

  asyncio.run(combined_loop())

CONTROLLER_CONFIGS.append(
  ControllerConfig(
    name="feed-121517",
    title="Feed 12/15/17 Control",
    module=feed_121517,
    max_diagnostics=1000,
    template="feed_121517.html",
    control_loop_handler=feed_121517_control_loop
  )
)

# Register all controllers
for config in CONTROLLER_CONFIGS:
  controller_manager.register_controller(config)

@app.route('/')
def home():
  """Home page with links to all controllers"""
  controllers = list(controller_manager.controllers.values())
  return render_template('home.html', controllers=controllers)

def create_routes():
  """Dynamically create routes for all controllers"""

  for config in CONTROLLER_CONFIGS:
    # Create view route
    def make_view_handler(config):
      def view_handler():
        return render_template(config.template,
                   title=config.title,
                   api_path=config.api_path,
                   controller_name=config.name)
      return view_handler

    app.add_url_rule(f'/{config.route_path}',
            f'{config.name}_index',
            make_view_handler(config))

    # Create diagnostics API route
    def make_diagnostics_handler(config):
      def diagnostics_handler():
        return jsonify(controller_manager.get_diagnostics(config.name))
      return diagnostics_handler

    app.add_url_rule(f'/api/{config.api_path}/diagnostics',
            f'get_{config.name}_diagnostics',
            make_diagnostics_handler(config))

    # Create parameters API route
    def make_parameters_handler(config):
      def parameters_handler():
        if request.method == 'POST':
          if hasattr(config.module, 'set_parameters'):
            config.module.set_parameters(request.json)
          else:
            # Handle restart_wp_11 special case
            params = request.get_json(force=True)
            config.module.set_parameters(params)
            return jsonify({'status': 'ok'})

        return jsonify(config.module.get_parameters())
      return parameters_handler

    app.add_url_rule(f'/api/{config.api_path}/parameters',
            f'{config.name}_parameters',
            make_parameters_handler(config),
            methods=['GET', 'POST'])

# Create all routes
create_routes()

if __name__ == '__main__':
  controller_manager.start_control_loops()
  app.run(host='localhost', port=5000)
