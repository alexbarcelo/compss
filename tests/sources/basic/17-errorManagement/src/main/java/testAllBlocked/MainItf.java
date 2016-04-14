package testAllBlocked;

import integratedtoolkit.types.annotations.Constraints;
import integratedtoolkit.types.annotations.Method;
import integratedtoolkit.types.annotations.Parameter;
import integratedtoolkit.types.annotations.Parameter.Direction;
import integratedtoolkit.types.annotations.Parameter.Type;

public interface MainItf 
{
	//No worker will satisfy this constraint, thus no workers available
	@Constraints(processorCoreCount = 999) 
	@Method(declaringClass="testAllBlocked.Main")
	Dummy normalTask
	(
			@Parameter(type = Type.INT, direction = Direction.IN) int x,
			@Parameter(type = Type.OBJECT, direction = Direction.IN) Dummy din
	);
}
