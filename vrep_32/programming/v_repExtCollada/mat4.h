// This file is part of the COLLADA PLUGIN for V-REP
// 
// Copyright 2006-2013 Dr. Marc Andreas Freese. All rights reserved. 
// marc@coppeliarobotics.com
// www.coppeliarobotics.com
// 
// The COLLADA PLUGIN is licensed under the terms of GNU GPL:
// 
// -------------------------------------------------------------------
// The COLLADA PLUGIN is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// The COLLADA PLUGIN is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with the COLLADA PLUGIN.  If not, see <http://www.gnu.org/licenses/>.
// -------------------------------------------------------------------
//
// This file was automatically created for V-REP release V3.0.1 on January 20th 2013

// Written by Alex Doumanoglou on behalf of Dr. Marc Freese

#pragma once
#include "vec3.h"

class mat4
{
private:
	double m_Mat[4][4];
public:
	mat4();
	mat4 operator*(const mat4& other) const;
	mat4& operator*=(const mat4& other);
	double& operator()(int row,int col);
	const double& operator()(int row,int col) const;

	static mat4 IdentityMatrix();
	static mat4 TranslationMatrix(const vec3& t);
	static mat4 RotationMatrix(vec3 axis,double angle);		// angle in degrees
	static mat4 ScaleMatrix(const vec3& s);
};
