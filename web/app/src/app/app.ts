import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppUpdate } from './app-update';

@Component({
  imports: [RouterOutlet, AppUpdate],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
}
